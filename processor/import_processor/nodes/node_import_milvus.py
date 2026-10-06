# processor/import_processor/nodes/node_import_milvus.py

import json
import logging
from typing import Dict, Any, List

from pymilvus import DataType

from config.milvus_config import milvus_config
from processor.import_processor.base import BaseNode, setup_logging
from processor.import_processor.exceptions import StateFieldError, MilvusError
from processor.import_processor.state import ImportGraphState
from utils.milvus_utils import get_milvus_client, escape_milvus_string


class NodeImportMilvus(BaseNode):
    """
    导入向量库节点（流水线第 ⑦ 步，终点站）：把内存里的成果落到三个库。

    一句话：**这是唯一"对外写"的节点。**
    state 几乎不变，但外部世界多了数据 —— 三个库里写进了东西。

    ── 位置 ───────────────────────────────────────────────────────────
    第 ⑦ 步，终点站。它跑完，整条导入流水线就结束了。

    ── 三个库各管什么 ─────────────────────────────────────────────────
      ┌──────────┬──────────────────────────────────────────────────┐
      │ Milvus   │ 向量 + 检索用元数据。RAG 真正查询的地方。         │
      │ (向量库) │ 写两张"表"：                                     │
      │          │   · chunks_collection     切片文本 + 向量         │
      │          │   · item_name_collection  主体名 + 向量（粗筛用） │
      ├──────────┼──────────────────────────────────────────────────┤
      │ MinIO    │ 原始文件、图片、转好的 MD。                       │
      │ (对象存储)│ 大文件都放这，Milvus 里只存一个路径字符串。      │
      ├──────────┼──────────────────────────────────────────────────┤
      │ MongoDB  │ 导入记录：任务编号、文件标题、切片数、时间、      │
      │ (文档库) │ 成功/失败状态。"查看导入历史"列表页就靠它。       │
      └──────────┴──────────────────────────────────────────────────┘
    这是 RAG 的标准三件套：向量库管**相似度**，对象存储管**大文件**，
    文档库管**结构化记录**。

    ── 写库前必须先做的事（不做一定写入失败）──────────────────────────
      ① 定义表结构：至少要有
             id（主键）、vector（向量，维度 = config.embedding_dim）、
             text（原文，检索命中后要返回给大模型的就是它）、
             source / title_path / chunk_index（元数据）
      ② 维度对齐：这里声明的维度和 ⑥ 的模型输出必须是同一个值。
      ③ 建索引：不建也能写入，但查询会慢到不可用。
      ④ 选相似度算法：.env 里有 MILVUS_METRIC_TYPE=COSINE /
         MILVUS_MIN_COSINE_SCORE=0.75，但 config 还没读它们，
         建议先补字段（见 config.py 缺口清单），别在节点里写死。

    ── 最重要的问题：同一文件导入两次会怎样？──────────────────────────
    不去重 → 库里出现两份一样的切片，检索时重复命中、浪费名额。
    常规解法（按推荐度）：
        ① 用"确定性主键"：id = md5(文件内容 + 段序号)。
           重复导入主键相同，用 upsert（有则覆盖）而不是 insert（只管插）。
           ✅ 最推荐 —— 天然去重。
        ② 导入前先按 source 删掉旧切片再插入。
           缺点：中途失败会留下"删了没写"的空窗。
        ③ 全量重建：简单粗暴，只适合小数据量。
    👉 "重复执行结果不变"这个性质叫**幂等**，是写库节点的生命线。

    ── 三个库写了一半失败怎么办 ───────────────────────────────────────
    三个库没法"一起撤销"。Milvus 写成了、MinIO 失败了，数据就不一致。
    实用做法：
        · 按 先 MinIO → 再 MongoDB → 最后 Milvus 的顺序写，
          Milvus 最后落（它是查询入口，宁可晚点出现）。
        · MongoDB 里记一条导入记录（状态 running → success/failed），
          失败时知道哪次是脏的，方便清理或补偿。
    """

    # name = "node_import_milvus"

    name: str = "node_import_milvus"

    def process(self, state: ImportGraphState) -> ImportGraphState:
        """
        把切片、向量、主体名分别写进三个库。

        输入（从 state 读的字段）：
            chunks : list
                哪来的：④ 切出来，⑥ 附上向量
                长什么样：[{"text": "...", "dense_vec": [0.12, ...],
                           "source": "...", "chunk_index": 0}, ...]
                什么时候有值：⑥ 跑完之后（向量在这一步才齐全）
            item_name : str   ← ⑤ 归纳出的主体名，写进 item_name_collection
            task_id : str     ← 外部调用方给的导入编号，写进 MongoDB 当记录主键
            file_title / md_path / file_dir : str
                              ← ② 给的，上传 MinIO 定位文件、写 MongoDB 当展示字段

        加工：
            1. 上传 MD / 图片到 MinIO，拿到路径
            2. 向 MongoDB 写一条导入记录（编号、标题、切片数、时间、状态）
            3. 组装数据，upsert 进 Milvus 的两张表
            ⚠️ 这一步不做数据加工，只是搬运。

        输出：
            建议返回：{"task_id": state["task_id"]}（只返回真变了的字段）
            或者干脆返回 {}（没改 state，只是写了外部库）。
            谁接手：**没有人** —— 它是最后一个节点，返回值没人用，
            但 LangGraph 要求返回字典，返回 {} 是合法的。

        副作用（最需要警惕的一步）：
            往三个外部库写数据。写了一半失败会留下脏数据，
            且三个库没法一起撤销 —— 所以"幂等"在这里比在任何节点都重要。
        """

        # ⚠️ 空实现占位 —— 目前"终点站"什么也没写，流水线跑完库是空的。
        # 期待的实现骨架：
        #     chunks = state["chunks"]
        #     # ① 上传 MD / 图片到 MinIO
        #     # ② 向 MongoDB 写一条导入记录
        #     # ③ 组装数据并 upsert 进 Milvus
        #     return {"task_id": state["task_id"]}
        #
        # 依赖预警：minio、pymongo 都装好了 ✅，但**没有 pymilvus** ——
        #          开工前要 uv add pymilvus，否则 import 直接失败。
        #
        # 异常建议：三个写入动作任何一个失败，都应该抛对应的错误类型：
        #     raise MilvusError(...) / MinioError(...) / MongoError(...)
        # exceptions.py 里前两个已备好（MongoError 还没定义，可顺手补上），
        # 这样上层能精准知道是哪个库出的问题。

        # 步骤1：输入数据有效性校验
        chunks_json_data, vector_dimension = self._step_1_check_input(state)

        # 步骤2：Milvus客户端连接+集合准备（自动建表）
        client = self._step_2_prepare_collection(vector_dimension)

        # 步骤3：幂等性处理 - 清理同file_title旧数据
        self._step_3_clean_old_data(client, chunks_json_data)

        # 步骤4：批量插入数据+主键chunk_id回填
        updated_chunks = self._step_4_insert_data(client, chunks_json_data)

        # 步骤5：更新全局状态，将回填后的切片回传下游
        state["chunks"] = updated_chunks

        return state


    def _step_1_check_input(self, state: Dict[str, Any]) -> tuple[List[Dict[str, Any]], int]:
        """
        步骤1：输入数据有效性校验
        核心校验项：
            1. chunks非空且为列表类型
            2. 切片包含dense_vector核心字段
            3. 提取向量维度，为集合创建/索引构建提供依据
        参数：
            state: Dict[str, Any] - 流程状态对象，包含上游传入的chunks数据
        返回：
            tuple - (校验通过的切片列表, 稠密向量维度)
        异常：
            任一校验项不通过，抛出ValueError终止入库流程，避免脏数据处理

        """

        # 校验1：chunks非空
        chunks = state.get("chunks")

        if not chunks:
            raise StateFieldError(field_name="chunks", message="chunks不能为空", expected_type=list)

        if not isinstance(chunks, list):
            raise StateFieldError(field_name="chunks", message="chunks数据类型不正确", expected_type=list)

        # 校验2：切片包含dense_vector字段
        first_chunk = chunks[0]
        if 'dense_vector' not in first_chunk:
            raise StateFieldError(field_name="chunks", message="错误: 数据中缺失dense_vector字段")

        # 校验3：切片包含 sparse_vector 字段
        if 'sparse_vector' not in first_chunk:
            raise StateFieldError(field_name="chunks", message="错误: 数据中缺失sparse_vector字段")

        # 提取向量维度
        vector_dimension = len(first_chunk['dense_vector'])
        return chunks, vector_dimension

    def _step_2_prepare_collection(self, vector_dimension: int):
        """
        步骤2：Milvus客户端连接+集合准备
        核心逻辑：
            1. 获取Milvus单例客户端，验证连接有效性
            2. 集合不存在则自动创建（Schema+索引），存在则直接复用
        参数：
            vector_dimension: int - 稠密向量维度（步骤1提取）
        返回：
            MilvusClient - 已连接、集合准备完成的客户端实例
        异常：
            客户端获取失败/集合名称未配置，抛出异常终止流程
        """

        # 1. 获取milvus客户端对象
        milvus_client = get_milvus_client()
        if not milvus_client:
            self.logger.error("Milvus 连接失败")
            raise MilvusError("Milvus 连接失败")

        # 2. 集合不存在则创建
        collections_name = milvus_config.chunks_collection
        if not milvus_client.has_collection(collections_name):
            self._create_chunks_collection(collections_name, milvus_client, vector_dimension)

        return milvus_client

    def _create_chunks_collection(self, collections_name, milvus_client, vector_dimension):

        # 1. 创建schem
        schema = milvus_client.create_schema(auto_id=True, enable_dynamic_field=True)
        # 2. 创建列
        schema.add_field(field_name="chunk_id", datatype=DataType.INT64, is_primary=True, auto_id=True)
        schema.add_field(field_name="content", datatype=DataType.VARCHAR, max_length=65535)  # 切片内容
        schema.add_field(field_name="title", datatype=DataType.VARCHAR, max_length=100)  # 切片标题
        schema.add_field(field_name="parent_title", datatype=DataType.VARCHAR, max_length=100)  # 父标题
        schema.add_field(field_name="part", datatype=DataType.INT8)  # 分片编号
        schema.add_field(field_name="file_title", datatype=DataType.VARCHAR, max_length=100)  # 源文件标题
        schema.add_field(field_name="item_name", datatype=DataType.VARCHAR, max_length=100)  # 商品名称（幂等性依据）
        schema.add_field(field_name="sparse_vector", datatype=DataType.SPARSE_FLOAT_VECTOR)  # 稀疏向量
        schema.add_field(field_name="dense_vector", datatype=DataType.FLOAT_VECTOR, dim=vector_dimension)  # 稠密向量

        # 3. 创建索引
        index_params = milvus_client.prepare_index_params()
        # 稠密向量索引：AUTOINDEX自动选最优索引类型+余弦相似度（语义检索常用）
        index_params.add_index(
            field_name="dense_vector",
            index_name="dense_vector_index",
            index_type="AUTOINDEX",
            metric_type="COSINE"
        )
        # 稀疏向量索引：专用SPARSE_INVERTED_INDEX+内积（IP），适配稀疏向量检索
        index_params.add_index(
            field_name="sparse_vector",
            index_name="sparse_inverted_index",
            index_type="SPARSE_INVERTED_INDEX",
            metric_type="IP",
            params={"inverted_index_algo": "DAAT_MAXSCORE", "normalize": True, "quantization": "none"}
        )

        # 创建集合
        milvus_client.create_collection(
            collection_name=collections_name,
            schema=schema,
            index_params=index_params
        )

    def _step_3_clean_old_data(self, client, chunks_json_data):

        """
        幂等清理
        基于每个片段的file_title进行旧数据的清理
        :param client: milvus客户端
        :param chunks_json_data: chunks数据
        :return:
        """

        # 1. 获取查询条件
        file_title = chunks_json_data[0].get("file_title")

        # 2. 执行幂等清理
        self._clear_chunks_by_file_title(client, file_title)

    def _clear_chunks_by_file_title(self, client, file_title):

        try:
            file_title = escape_milvus_string(file_title)
            client.delete(
                collection_name=milvus_config.chunks_collection,
                filter=f"file_title=='{file_title}'")
        except Exception as e:
            self.logger.error(f"Milvus 数据删除失败: {str(e)}")
            raise MilvusError(f"Milvus 数据删除失败: {str(e)}")

    def _step_4_insert_data(self, client, chunks_json_data):
        """
        步骤4：批量插入切片数据到Milvus+主键回填
        核心逻辑：
            1. 批量插入数据：提升入库效率，减少Milvus连接次数
            2. 回填chunk_id：将Milvus生成的自增主键回填到切片，供下游业务使用
        参数：
            client - MilvusClient实例
            chunks_json_data: List[Dict[str, Any]] - 待入库的切片列表
        返回：
            List[Dict[str, Any]] - 回填了chunk_id的切片列表
        """
        # 1. 填充part字段
        for item in chunks_json_data:
            item["part"] = 0

        # 2. 批量插入数据
        result = client.insert(
            collection_name=milvus_config.chunks_collection,
            data=chunks_json_data
        )

        # 3. 回填chunk_id
        inserted_ids = result.get("ids")
        for idx, item in enumerate(chunks_json_data):
            item["chunk_id"] = inserted_ids[idx]

        return chunks_json_data

if __name__ == "__main__":

    setup_logging()

    json_path = r"E:\doc\hak180产品安全手册\state_vector.json"
    with open(json_path, "r", encoding="utf-8") as f:
        state_json = f.read()

    state = json.loads(state_json)

    init_state = {
        "chunks": state.get("chunks")
    }

    # 执行核心处理流程
    node_import_milvus = NodeImportMilvus()
    result = node_import_milvus(init_state)

    logging.getLogger().info(json.dumps(result, ensure_ascii=False, indent=4))