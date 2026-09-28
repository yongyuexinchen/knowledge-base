# processor/import_processor/nodes/node_document_split.py

from processor.import_processor.base import BaseNode
from processor.import_processor.state import ImportGraphState


class NodeDocumentSplit(BaseNode):
    """
    文档切分节点（流水线第 ④ 步）：把一篇长文切成若干小段。

    一句话：**把一根长绳子剪成若干段**。之后的向量化、检索都以"段"为单位。

    ── 位置 ───────────────────────────────────────────────────────────
    第 ④ 步。两条支路（PDF / MD）在这里汇合，之后的步骤完全一样。

    ── 为什么必须切？三个硬约束 ───────────────────────────────────────
      ① 模型吃不下整篇：向量模型有最大输入长度（BGE-M3 是 8192 token）。
      ② 检索要精准：整篇当一个向量，用户问"设备安装间距是多少"，
         你返回 50 页 —— 既费 token 又不准。段太大噪声多，太小语义不完整，
         **切多大是 RAG 里最关键的调参项**。
      ③ 要能溯源：每段带着"来自哪个文件、哪个章节"，
         前端"查看原文"靠的就是它。

    ── 用到 config 里的四个参数（这是本节点的核心）────────────────────
        max_content_length = 2000   每段字数上限
                                    太小 → 一句话被切两半；太大 → 检索不精准
        min_content_length = 500    下限，比这短的碎片尝试和相邻段合并
                                    （标题、短段落会产生极短的段，单独做向量没信息量）
        overlap_sentences = 1       相邻段重叠的句数
                                    防止语义正好在切分点被切断：
                                    "……因此该参数应设置为" | "1.5 倍额定值。"
                                    两段各自都读不出完整意思，重叠 1 句就好了。
        image_extensions            判断某段是不是图片引用，别把它当正文切

    ── 用什么工具切 ───────────────────────────────────────────────────
    项目已装好 langchain-text-splitters，两个最该用的类：
        MarkdownHeaderTextSplitter     按 # / ## / ### 标题层级切，
                                       自动记住每段属于哪个章节
        RecursiveCharacterTextSplitter 对超长的段再按 段落→换行→句号→空格
                                       的优先级继续拆，尽量在自然边界断开
    典型组合：先用前者按结构切，再用后者控制长度。
    """

    name = "node_document_split"

    def process(self, state: ImportGraphState):
        """
        按标题层级 + 长度上限，把整篇正文切成 chunks（切片列表）。

        输入（从 state 读的字段）：
            md_content : str
                哪来的：③ 处理完图片后写进去的正文
                长什么样："# 第三章 安装要求\n\n## 3.1 间距\n\n设备间距应不小于..."
                什么时候有值：③ 跑完之后

        还会读 config 的四个参数（不从 state 读，从 self.config 读）：
            max_content_length / min_content_length / overlap_sentences / image_extensions

        加工：
            1. 先按 #/##/### 标题层级切 → 每段自动带上章节路径
            2. 超长的段，再按 段落→换行→句号→空格 的优先级继续拆
            3. 过短的段（< 500 字），尝试和相邻段合并
            4. 相邻段之间保留 1 句重叠
            5. 给每段编上序号

        输出：
            建议返回：{"chunks": [ {...}, {...}, ... ]}
            每段长这样（元数据是给检索过滤用的，务必保留）：
                {
                  "text": "……正文……",
                  "source": "某设备手册.pdf",       # 来自哪个文件
                  "title_path": "第三章 > 安装要求", # 章节路径，用于展示和过滤
                  "chunk_index": 12,               # 序号，用于排序
                }
            谁接手：⑤（取前 3 段认主体）、⑥（每段转向量）、⑦（写入库）
        """

        # ⚠️ 空实现占位。
        # 期待的实现骨架：
        #     md = state["md_content"]
        #     chunks = split_by_headers_then_length(md, self.config)  # 用上面四个参数
        #     return {"chunks": chunks}   # ← 只返回自己改动的字段
        #
        # 提醒：参数一定要从 self.config 读（父类 __init__ 已经备好了），
        # 别在代码里写死 2000 这种数字 —— 否则 config.py 就形同虚设。
        return state
