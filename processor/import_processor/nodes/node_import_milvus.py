# processor/import_processor/nodes/node_import_milvus.py

from processor.import_processor.base import BaseNode
from processor.import_processor.state import ImportGraphState


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

    name = "node_import_milvus"

    def process(self, state: ImportGraphState):
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
        return state
