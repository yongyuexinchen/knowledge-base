# processor/import_processor/nodes/node_item_name_recognition.py

from processor.import_processor.base import BaseNode
from processor.import_processor.state import ImportGraphState


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

    def process(self, state: ImportGraphState):
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
        return state
