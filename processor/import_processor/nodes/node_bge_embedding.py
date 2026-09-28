# processor/import_processor/nodes/node_bge_embedding.py

from processor.import_processor.base import BaseNode
from processor.import_processor.state import ImportGraphState


class NodeBGEEmbedding(BaseNode):
    """
    向量化节点（流水线第 ⑥ 步）：把文字变成数字向量。

    一句话：**给每段文字配一个"语义坐标"。**
    之后检索时，用户的问题也转成坐标，找离得最近的几段文字 —— 这就是 RAG 的核心。

    ── 位置 ───────────────────────────────────────────────────────────
    第 ⑥ 步（最后一步计算），之后 ⑦ 就是纯写库了。

    ── BGE-M3 这个模型强在哪 ──────────────────────────────────────────
    它跑一次能同时产出三种"文字表示"：
      ① 稠密向量（dense）：1024 维数字数组。
         强在语义 —— "苹果手机"和"iPhone"的坐标很近，哪怕字面完全不同。
         弱在精确匹配 —— 型号、编号（如"GT-2000A"）容易对不上。
      ② 稀疏词权（sparse）：类似"关键词权重表" {词: 权重}。
         强在精确匹配 —— 查"GT-2000A"必命中含这个词的文档。
         弱在不懂同义词（"设备"和"机器"它当成两个词）。
      ③ 多向量（colbert）：每个词一个向量，精度最高但最占地方。
    实际用法是 ①+② 两路各查一遍再合并结果（叫"混合检索"），
    一套模型供两路 —— 这是它最大的工程价值。

    ── 用到 config 里的参数 ───────────────────────────────────────────
        embedding_dim            向量维度。**必须和建库时声明的维度完全一致**，
                                 否则写入时报维度不匹配（最常见的联调故障）。
                                 ⚠️ 实测冲突：.env 里 EMBEDDING_DIM=1536
                                    （对应云端模型 text-embedding-v4），
                                    而本地 BGE-M3 是 1024 维 —— 两套方案在打架，
                                    动手前必须先选定一套（详见 config.py）。
        embedding_batch_size = 8 一次送多少条文本给模型。
                                 太小跑不满 GPU；太大显存溢出。

    ── 开工前的两个硬问题（已实测）────────────────────────────────────
      ① 依赖没装：.venv 里没有 torch / FlagEmbedding / sentence-transformers
         任何一个 —— 目前根本没有能跑这个模型的库。开工前：
             uv add FlagEmbedding     # BAAI 官方库，支持三路输出（推荐）
      ② config 缺字段：BGE_M3_PATH（模型路径）、BGE_DEVICE（cuda:0）、
         BGE_FP16（半精度）这些键在 .env 里有，但 ImportConfig 没读，
         要先补字段（见 config.py 缺口清单）。
         另外 BGE_DEVICE=cuda:0 表示要求 N 卡 —— 没显卡就改成 "cpu"（会慢不少）。

    ── 性能提醒 ───────────────────────────────────────────────────────
    一定要成批送（一次 batch_size 条），千万别 for 循环一条条算 —— 慢一个数量级。
    """

    name = "node_bge_embedding"

    def process(self, state: ImportGraphState):
        """
        成批把每段的 text 转成向量，挂回对应的段上。

        输入（从 state 读的字段）：
            chunks : list
                哪来的：④ 切好的切片列表
                长什么样：[{"text": "设备间距应不小于…", "chunk_index": 0}, ...]
                什么时候有值：④ 跑完之后
                怎么用：texts = [c["text"] for c in state["chunks"]]

        还会读 config：embedding_batch_size / embedding_dim

        加工：
            1. 从 chunks 里抽出所有 text，组成一个列表
            2. 成批喂给模型：model.encode(texts, batch_size=8)
            3. 拿到一批 numpy 数组（每条形如 array([0.12, -0.34, ...])）
            4. 转成 Python 原生列表：vec.tolist()
               （numpy 数组不能直接塞给向量库，要先转）
            5. 把每个向量挂回对应的段上
            ⚠️ 这步是纯计算：不产生新内容，只是给已有数据"加一列"。

        输出：
            建议返回：{"chunks": chunks}   ← 改过的**同一批** chunks
            每段多了一个键：
                {"text": "...", "chunk_index": 0, "dense_vec": [0.12, -0.34, ...]}
            谁接手：⑦ —— 把 text + dense_vec + 元数据写进向量库

        一个值得留意的设计问题：向量往哪放？
            方案 A（上面这样）：塞回 state["chunks"]，每段多一个键。
                简单直观，但 state 会瞬间膨胀（一个 1024 维向量写成
                Python 列表就是 1024 个数字，很占内存）。
            方案 B：向量不进 state，⑥⑦ 之间用本地临时文件传，或干脆合并成一个节点。
            建议：段数不多（< 几千）用 A 图省事；上量后换 B。
        """

        # ⚠️ 空实现占位。
        # 期待的实现骨架：
        #     chunks = state["chunks"]
        #     texts = [c["text"] for c in chunks]
        #     vecs = model.encode(texts, batch_size=self.config.embedding_batch_size)
        #     for c, v in zip(chunks, vecs):
        #         c["dense_vec"] = v.tolist()      # numpy 数组要先转成原生列表
        #     return {"chunks": chunks}            # ← 把向量"附着"回 chunks 上
        return state
