# processor/import_processor/nodes/node_item_name_recognition.py

import json
import logging
from http.client import responses
from typing import Tuple, Dict, List

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from pyexpat.errors import messages
from pymilvus import DataType

from config.lm_config import lm_config
from config.milvus_config import milvus_config
from processor.import_processor.base import BaseNode, setup_logging
from processor.import_processor.exceptions import StateFieldError
from processor.import_processor.state import ImportGraphState
from utils.embedding_utils import generate_embeddings
from utils.milvus_utils import get_milvus_client, escape_milvus_string


class NodeItemNameRecognition(BaseNode):
    """
    主体识别节点（流水线第 ⑤ 步）：用大模型归纳"这篇文档讲的是什么"。

    一句话：**把一堆文字压缩成一个标签**，比如 "螺纹钢"。

    ── 位置 ───────────────────────────────────────────────────────────
    第 ⑤ 步（切分之后、向量化之前）。

    ── 它解决什么业务问题 ─────────────────────────────────────────────
    假设你导入了 300 份研报，用户问"螺纹钢库存情况"。
    你希望只在那几份**关于螺纹钢**的文档里找，而不是 300 份全翻一遍。
    所以需要一个"主体标签"来缩小范围。
    问题是：文件名靠不住（"2026年3月报.pdf" 看不出讲什么），
    正文里也未必有一句"本文讲的是螺纹钢" —— 所以用大模型来归纳。

    ── 用到 config 里的两个参数（专为省 token 设计）──────────────────
        item_name_chunk_k = 3        只取前 3 段喂给大模型
                                     为什么不是全部？判断"文档主题"看开头就够
                                     （标题、摘要、导语都在前面），
                                     全文喂进去 token 成本翻十倍
        item_name_chunk_size = 2500  每段只截取前 2500 字
                                     3 × 2500 = 7500 字 ≈ 5k token，够用
    👉 这是"用少量样本换低成本"的设计 —— 识别主体是"够用就行"的任务。

    ── 用哪个模型 ─────────────────────────────────────────────────────
    config 里单独有个 item_model，和主模型分开 ——
    轻任务配便宜模型，重活配好模型，是务实的省钱做法。

    ── 工程上必须注意的两点 ───────────────────────────────────────────
      ① 大模型会说废话（"根据文档内容，该文档主要讲述的是螺纹钢"）。
         必须约束它只返回一个词，否则 item_name 会带一堆杂质。
         失败时要有兜底（比如拿文件名当 item_name）。
      ② 不要静默失败：大模型会超时、会被限流。
         出错应该 raise LLMError(...)（exceptions.py 已备好），
         别吞掉错误返回空串 —— 下游会拿到空标签却毫不知情。
    """

    name = "node_item_name_recognition"

    def process(self, state: ImportGraphState) -> ImportGraphState:
        """
        取前几段喂给大模型，让它回答"这篇文档的主角是谁"。

        输入（从 state 读的字段）：
            chunks : list
                哪来的：④ 切好的切片列表
                长什么样：[{"text": "……", "source": "...", "chunk_index": 0}, ...]
                什么时候有值：④ 跑完之后
                怎么用：chunks[: self.config.item_name_chunk_k]  ← 只取前 3 段

        还会读 config：item_name_chunk_k / item_name_chunk_size / item_model

        加工：
            1. 取前 3 段，把它们的 text 拼起来
            2. 截断到 7500 字以内（控制 token）
            3. 调大模型，提示词大意：
                   "以下是一份文档的开头，请只返回它讲的主体名称，不要解释"
            4. 清洗模型返回（可能带杂质）
            ⚠️ 这步是**概率性**的：同样输入跑两次，答案可能不同。

        输出：
            建议返回：{"item_name": "螺纹钢"}
            谁接手：⑦ —— 写进向量库，检索时"先按主体粗筛、再在文档内精查"

        副作用：调一次外部付费 API（产生 token 费用）。
        """

        # ⚠️ 空实现占位。
        # 期待的实现骨架：
        #     chunks = state["chunks"][: self.config.item_name_chunk_k]
        #     sample = "".join(c["text"] for c in chunks)[: self.config.item_name_chunk_size]
        #     item_name = call_llm(self.config.item_model, prompt, sample)
        #     return {"item_name": item_name}      # ← 只返回自己改动的字段
        #
        # 顺序提醒：这个节点必须在 ④ 之后跑（要用 chunks）。
        # 图的连线顺序配错了，这里会报 KeyError —— 排查时查 docs/FLOW.md 的对照表。
        file_title, chunks = self._step_1_get_inputs(state)

        # 步骤2：构建大模型识别的上下文
        context = self._step_2_build_context(chunks)

        # 步骤3：调用大模型识别商品名称
        item_name = self._step_3_call_llm(file_title, context)

        # 步骤4：回填商品名称到状态和切片
        self._step_4_update_chunks(state, chunks, item_name)

        # 步骤5：为商品名称生成稠密/稀疏向量
        dense_vector, sparse_vector = self._step_5_generate_vectors(item_name)

        # 步骤6：将数据存入Milvus向量数据库
        self._step_6_save_to_milvus(state, file_title, item_name, dense_vector, sparse_vector)

        # 打印识别结果
        self.logger.info(f"--- 识别完成: {item_name} ---")

        return state

    def _step_1_get_inputs(self, state: ImportGraphState) -> Tuple[str, List[Dict]]:
        """
        步骤 1: 接收并校验流程输入
        核心作用：
            1. 从流程状态中提取文件标题、文本切片核心数据
            2. 基础数据类型校验，保证下游流程输入有效性
        依赖的状态数据（上游节点产出）：
            - state["file_title"]: 上游提取的文件标题
            - state["chunks"]: 文本切片列表
        返回值：
            Tuple[str, List[Dict]]: (处理后的文件标题, 校验后的文本切片列表)
        """

        # 1、参数校验
        file_title = state.get("file_title")
        if not file_title:
            raise StateFieldError(field_name="file_title", message="文件标题不能为空", expected_type=str)

        chunks = state.get("chunks")
        if not chunks:
            raise StateFieldError(field_name="chunks", message="chunks不能为空", expected_type=list)

        if not isinstance(chunks, list):
            raise StateFieldError(field_name="chunks", message="chunks数据类型不正确", expected_type=list)

        return file_title, chunks

    def _step_2_build_context(self, chunks: List[Dict]) -> str:
        """
        步骤 2: 构造大模型商品名称识别的标准化上下文
        核心作用：
            1. 限制切片数量：仅取前k个切片，避免上下文过长
            2. 限制字符长度：总上下文字符限制，适配大模型输入上限
            3. 格式化内容：带序号的结构化格式，提升大模型识别精度
        参数说明：
            chunks: 文本切片列表
        返回值：
            str: 格式化后的上下文字符串
        """

        parts: List[str] = []
        total_chars = 0
        for idx, chunk in enumerate(chunks[:self.config.item_name_chunk_k], start = 1):

            # 1. 提取前k的切片，避免上下文过长
            chunk_title = chunk.get("title").strip()
            chunk_content = chunk.get("content").strip()

            # 2. 格式化切片
            piece = f"【切片{idx}】\n标题{chunk_title}\n内容：{chunk_content}"
            parts.append(piece)

            # 3. 计算累计的字符数
            total_chars += len(piece)

            # 4. 判断是否需要继续切分
            if total_chars > self.config.item_name_chunk_size:
                self.logger.warning(f"累计字符数{total_chars}已超过限制{self.config.item_name_chunk_size}，停止切分")
                break

        # 5. 使用换行符对切分后的片段进行连接
        context = "\n\n".join(parts).strip()

        # 6. 对返回结果进行二次截断
        final_context = context[:self.config.item_name_chunk_size]

        return final_context

    def _step_3_call_llm(self, file_title: str, context: str) -> str:
        """
        步骤 3: 调用大模型实现商品名称/型号精准识别
        核心逻辑：
            1. 上下文为空 → 直接返回file_title（兜底，无需调用大模型）
            2. 上下文非空 → 加载标准化prompt模板，构建大模型对话消息
            3. 调用大模型后对返回结果做清洗，过滤无效字符
            4. 大模型返回空/调用异常 → 均返回file_title兜底，保证流程不中断
        核心特性：
            - 提示词解耦：通过load_prompt加载本地模板，无需硬编码
            - 格式兼容：兼容不同LLM客户端返回格式，防止属性报错
            - 异常兜底：全异常捕获，大模型服务不可用时不影响主流程
        参数：
            file_title: 处理后的文件标题（异常/空值时的兜底值）
            context: 步骤2构建的结构化切片上下文（大模型识别的核心依据）
        返回值：
            str: 清洗后的商品名称（异常/空值时返回原始file_title）
        """

        # 1. 上下文为空，返回file_title
        if not context:
            return file_title

        # 2. 大模型调用
        try:
            # 2.1 加载提示词模板
            prompt = f"""
请从以下信息中识别出商品名称与型号：
文件名：{file_title}

正文切片（用于辅助识别）：
{context}

要求：
1. 返回内容为字符串形式，最好是带品牌、型号和名称的完整商品名称。比如：苏伯尓5000W大功率电磁炉；
2. 返回结果应该只包含商品名称，不要添加任何解释或其他内容；
3. 如果无法识别商品名称,请返回空字符串。
"""
            # 2.2 初始化大模型客户端
            llm = ChatOpenAI(
                model=lm_config.llm_model,
                api_key=lm_config.api_key,
                base_url=lm_config.base_url,
                temperature=lm_config.llm_temperature,
                extra_body={"enable_thinking": False}
            )

            # 2.3 创建消息对象
            messages = [
                SystemMessage(content="你是一个专业的商品名称识别模型，请根据提供的信息，识别商品名称。"),
                HumanMessage(content=prompt)
            ]

            # 2.4 模型调用
            response = llm.invoke(messages)
            item_name = response.content

            # 2.5 数据清洗
            item_name = (item_name.replace(" ", "")
                         .replace("\n", "")
                         .replace("\t", "")
                         .replace("\r", ""))

            # 2.6 如果返回空字符串
            if not item_name:
                return file_title

            return item_name

        except Exception as e:
            self.logger.error(f"大模型调用异常：{e}")
            return file_title

    def _step_4_update_chunks(self, state: ImportGraphState, chunks: List[Dict[str, str]], item_name: str):
        """
        步骤 4: 回填商品名称到流程状态和所有文本切片
        核心作用：
            1. 全局状态更新：将item_name存入state，供下游所有节点直接使用
            2. 切片数据补全：为每个切片添加item_name字段，保证数据一致性
            3. 状态同步：更新state中的chunks，确保切片修改全局生效
        设计思路：
            所有切片关联同一商品名称，保证后续向量入库、检索时的维度一致性
        参数：
            state: 流程状态对象
            chunks: 校验后的文本切片列表
            item_name: 步骤3识别并清洗后的商品名称
        """

        state["item_name"] = item_name

        for chunk in chunks:
            chunk["item_name"] = item_name

        state["chunks"] = chunks

    def _step_5_generate_vectors(self, item_name: str) -> Tuple[List, Dict]:
        """
        步骤 5: 为商品名称生成 BGE-M3 稠密 + 稀疏双向量（Milvus 向量检索核心）
        核心说明：
            - 稠密向量（dense_vector）：BGE-M3 固定 1024 维，记录文本深层语义信息
            - 稀疏向量（sparse_vector）：变长键值对，记录文本关键词/特征位置信息
        依赖工具：
            generate_embeddings：封装 BGE-M3 模型，批量生成双向量，兼容单条/批量输入
        参数：
            item_name: 步骤 3 识别的商品名称（非空，空值时直接返回空向量）
        返回值：
            Tuple[List, Dict]: (稠密向量列表，稀疏向量字典)
        """

        # 1. 空值时直接返回空向量
        if not item_name:
            return None, None

        # 2. 使用向量模型生成稠密向量和稀疏向量
        vectors = generate_embeddings([item_name])
        return vectors["dense"][0], vectors["sparse"][0]

    def _step_6_save_to_milvus(self, state: ImportGraphState, file_title: str, item_name: str, dense_vector,
                               sparse_vector):
        """
        步骤 6: 将商品名称、文件标题、双向量持久化到 Milvus 向量数据库
        核心逻辑：
            1. 客户端获取：获取单例 Milvus 客户端，连接失败则跳过
            2. 集合初始化：无集合则创建（定义 Schema+索引），有集合则直接使用
            3. 幂等性处理：删除同名商品数据，避免重复存储
            4. 数据插入：构造符合 Schema 的数据，非空向量才添加
        参数：
            state: 流程状态对象，用于最终状态同步
            file_title: 处理后的文件标题
            item_name: 识别后的商品名称（主键去重依据）
            dense_vector: 步骤 5 生成的稠密向量（1024 维列表）
            sparse_vector: 步骤 5 生成的稀疏向量（字典格式）
        """


        # 1. 获取 Milvus 客户端
        milvus_client = get_milvus_client()
        if not milvus_client:
            # 降级处理
            self.logger.warning("Milvus 连接失败，跳过设备名称保存")
            return
        try:
            # 2. 集合初始化
            collection_name = milvus_config.item_name_collection

            # 判断集合是否已经被创建
            if not milvus_client.has_collection(collection_name):
                self._create_item_name_collection(collection_name, milvus_client)

            # 3. 幂等性处理：删除同名商品数据，避免重复存储
            file_title = escape_milvus_string(file_title)
            milvus_client.delete(collection_name=collection_name, filter=f"file_title=='{file_title}'")

            # 4. 数据插入：构造符合 Schema 的数据，非空向量才添加
            data = {
                "file_title": file_title,
                "item_name": item_name
            }

            if dense_vector is not None:
                data["dense_vector"] = dense_vector
            if sparse_vector is not None:
                data["sparse_vector"] = sparse_vector

            milvus_client.insert(collection_name=collection_name, data=data)


        except Exception as e:
            # 降级处理
            self.logger.warning(f"数据存入Milvus失败，跳过设备名称保存，错误原因:{str(e)}")

    def _create_item_name_collection(self, collection_name, milvus_client):

        # 1. 创建schema
        schema = milvus_client.create_schema(auto_id=True, enable_dynamic_field=True)

        # 2. 创建字段
        # 添加主键字段（INT64类型，自增）
        schema.add_field(
            field_name="pk",
            datatype=DataType.INT64,
            is_primary=True,
            auto_id=True
        )

        # 添加文件标题字段（VARCHAR类型，最大长度65535）
        schema.add_field(
            field_name="file_title",
            datatype=DataType.VARCHAR,
            max_length=100
        )

        # 添加商品名称字段（VARCHAR类型，最大长度65535）
        schema.add_field(
            field_name="item_name",
            datatype=DataType.VARCHAR,
            max_length=100
        )

        # 添加稠密向量字段（FLOAT_VECTOR类型，1024维，BGE-M3模型固定维度）
        schema.add_field(
            field_name="dense_vector",
            datatype=DataType.FLOAT_VECTOR,
            dim=1024
        )

        # 添加稀疏向量字段（SPARSE_FLOAT_VECTOR类型，变长，适配BGE-M3的稀疏向量）
        schema.add_field(
            field_name="sparse_vector",
            datatype=DataType.SPARSE_FLOAT_VECTOR
        )

        # 3. 构建索引参数（提升向量检索性能）
        index_params = milvus_client.prepare_index_params()
        # 为稠密向量创建索引（IVF_FLAT：兼容性好，适合小数据量）
        # 核心是 “先聚类分桶、再桶内暴力精确检索”。
        index_params.add_index(
            field_name="dense_vector",  # 字段名
            index_name="dense_vector_index",  # 索引名
            index_type="IVF_FLAT",  # 索引类型（兼容所有Milvus版本）
            metric_type="COSINE",  # 相似度计算方式（余弦相似度）
            params={"nlist": 128}  # 聚类数（影响检索精度/速度）
        )

        # 为稀疏向量创建索引（SPARSE_INVERTED_INDEX：稀疏向量专用索引）
        index_params.add_index(
            field_name="sparse_vector",  # 字段名
            index_name="sparse_vector_index",  # 索引名
            index_type="SPARSE_INVERTED_INDEX",  # 索引类型
            metric_type="IP",  # 相似度计算方式（内积）
            params={
                "inverted_index_algo": "DAAT_MAXSCORE",
                # 高效的稀疏检索算法

                "normalize": True,
                # ↑ L2 归一化，让内积 (IP) 等价于余弦相似度

                "quantization": "none"
                # ↑ 关闭量化，保持原始精度：模型生成的向量已经压缩的一半的精度了（BGE_FP16=1），这里就不再压缩了
                # "quantization": "none" → 存储原始向量，不压缩
                # "quantization": "sq8" → 存储压缩后的向量（8-bit 量化
            })

        # 4. 创建集合（Schema + 索引）
        milvus_client.create_collection(
            collection_name=collection_name,
            schema=schema,
            index_params=index_params
        )


if __name__ == "__main__":

    setup_logging()

    json_path = r"E:\doc\hak180产品安全手册\chunks.json"
    with open(json_path, "r", encoding="utf-8") as f:
        chuncks_json = f.read()

    chuncks = json.loads(chuncks_json)

    init_state = {
        "chunks": chuncks,
        "file_title": "hak180产品安全手册"
    }

    # 执行核心处理流程
    node_item_name_recognition = NodeItemNameRecognition()
    result = node_item_name_recognition(init_state)

    logging.getLogger().info(json.dumps(result, ensure_ascii=False, indent=4))