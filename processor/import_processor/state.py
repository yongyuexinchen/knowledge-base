# processor/import_processor/state.py

r"""
流程状态定义：贯穿全流程的那张大字典长什么样
================================================================================
整个项目流转的数据只有一份：一个大字典，叫 state。
每个节点从里面读自己要的字段，再把自己改动的字段写回去。

    上一个节点 ──state──▶ 本节点 process() ──改动的字段──▶ LangGraph 合并 ──▶ 下一节点

这个文件里的三样东西：
    ImportGraphState     字段清单：state 里有哪些字段、各是什么类型
    GRAPH_DEFAULT_STATE  空白模板：每个字段的初始值
    get_default_state()  每次新任务调一次，拿一份模板的完整复制品

【每个字段下面标了三件事，读代码时按这个查】
    【谁写】哪个节点负责往这个字段放值
    【谁读】哪个节点会取这个字段
    【何时】什么时候它才有值（在那之前读，拿到的是空串/空列表）

【TypedDict 是什么】（详见 docs/CONCEPTS.md §8）
    写法像"带类型的字典"。注意：它**只是给 IDE 看的提示**，
    让编辑器能自动补全 state["..."]、拼错字段名会标红。
    运行时 Python 完全不检查 —— 少字段、类型错都不报错。

【一处文档与代码不符，知道即可】
    下面的类写作 class ImportGraphState(TypedDict)，没有加 total=False。
    意思是"严格来说每个字段都该有值"。但节点们实际只返回少数字段，
    类型检查工具会对此不满（运行没有任何影响）。
    想彻底干净，把类改成 class ImportGraphState(TypedDict, total=False) 即可。
"""

from typing import TypedDict, List

import copy


class ImportGraphState(TypedDict):
    """导入流程的完整字段清单。各字段的【谁写/谁读/何时】见下方注释。"""

    # ── 任务标识 ─────────────────────────────────────────────────────────
    task_id: str
    # 【谁写】外部调用方（提交任务时给的），目前没有节点写它
    # 【谁读】NodeImportMilvus ⑦ —— 写 MongoDB 时当这次导入的唯一编号
    # 【何时】一开始就该有；没给就是空串 ""

    # ── 分支开关（决定下一步走哪条路）─────────────────────────────────────
    is_md_read_enabled: bool
    # 【谁写】NodeEntry ① —— 输入文件是 .md 就置 True
    # 【谁读】LangGraph 的路由函数（不是节点），读它决定要不要跳过 PDF 转换
    # 【何时】① 跑完之后

    is_pdf_read_enabled: bool
    # 【谁写】NodeEntry ① —— 输入文件是 .pdf 就置 True
    # 【谁读】路由函数
    # 【何时】① 跑完之后

    # ── 路径信息（文件在各阶段的位置）─────────────────────────────────────
    import_file_path: str
    # 【谁写】外部调用方 —— 这就是整条流水线的"输入"本身，不是任何节点写的
    # 【谁读】NodeEntry ①（看后缀）、NodePDFToMD ②（解析这个文件）
    # 【何时】一开始就有，必须有值，否则整条链没法跑

    file_dir: str
    # 【谁写】NodePDFToMD ② —— 本次任务的输出目录（图片、中间产物放这）
    # 【谁读】NodeMDImg ③（图片往哪存）
    # 【何时】② 跑完之后

    pdf_path: str
    # 【谁写】⚠️ 目前没有任何节点写它 —— 要么补，要么删掉这个字段
    # 【谁读】暂无
    # 【何时】永远是空串

    md_path: str
    # 【谁写】NodePDFToMD ② —— 转出来的 .md 文件的存放路径（只存路径，不存内容）
    # 【谁读】NodeMDImg ③、NodeDocumentSplit ④（按路径去读文件）
    # 【何时】② 跑完之后

    # ── 文件信息 ─────────────────────────────────────────────────────────
    file_title: str
    # 【谁写】NodePDFToMD ② —— 原文件名去掉扩展名
    # 【谁读】NodeDocumentSplit ④ —— 当切片的"来源标签"，检索时能显示出处
    # 【何时】② 跑完之后

    item_name: str
    # 【谁写】NodeItemNameRecognition ⑤ —— 用大模型从正文归纳出的主体名（如"螺纹钢"）
    # 【谁读】NodeImportMilvus ⑦ —— 写进向量库，检索时先按它粗筛
    # 【何时】⑤ 跑完之后
    # 注意：它是大模型的产出，不是精确计算 —— 同样输入跑两次结果可能不同。

    # ── 中间数据 ─────────────────────────────────────────────────────────
    md_content: str
    # 【谁写】NodeMDImg ③ —— 图片描述回填后的正文
    # 【谁读】NodeDocumentSplit ④ —— 切分用的就是它
    # 【何时】③ 跑完之后
    # ⚠️ 流程矛盾点：② 的注释说"正文不进 state，只存路径"，
    #    但 ③④ 都假设 md_content 里有正文。两种做法要先定一种（见 docs/FLOW.md 第四节）。

    chunks: List
    # 【谁写】NodeDocumentSplit ④ 写入切片列表；NodeBGEEmbedding ⑥ 给每个切片附上向量
    # 【谁读】⑤⑥⑦
    # 【何时】④ 跑完之后
    # 每个元素长这样（规划）：
    #     {"text": "正文", "source": "某手册.pdf",
    #      "title_path": "第三章 > 安装要求", "chunk_index": 12}
    # ⚠️ List 后面没写元素类型，等于放弃检查。建议改成 List[dict]。


# ── 空白模板 ────────────────────────────────────────────────────────────────
# 它是"初始状态"的样板，每个字段的默认值都写在这里。
# 【谁写】没有任何人写它 —— 它只在下面被复制
# 【谁读】get_default_state()
GRAPH_DEFAULT_STATE: ImportGraphState = {
    "task_id": "",

    "is_pdf_read_enabled": False,   # 默认两个分支都关着，由入口节点决定开哪个
    "is_md_read_enabled": False,

    "file_dir": "",
    "import_file_path": "",
    "pdf_path": "",
    "md_path": "",
    "file_title": "",
    "md_content": "",

    # ⚠️ 注意：空列表是"会变的对象"。如果有人直接往这个全局列表里塞东西，
    #    模板就被永久污染了 —— 下次新任务会凭空多出上一次的切片。
    #    这就是下面必须提供 get_default_state() 复制一份的原因。
    "chunks": [],

    "item_name": "",
}


def get_default_state() -> ImportGraphState:
    """
    拿一份全新的空白 state，每次新任务开始前调一次。

    输入：无参数。数据来源是上面的全局模板 GRAPH_DEFAULT_STATE。

    加工：把模板**完整复制一份**（连里面的空列表也复制成新的）。

    输出：一份全新的 state 字典，交给外部调用方。典型用法：
            app.invoke(get_default_state() | {"import_file_path": "D:/a.pdf"})
                                        ↑ 在这里把真正的输入塞进去

    为什么不能直接 return GRAPH_DEFAULT_STATE？
        Python 里变量是"标签"，直接返回等于把同一份字典给了调用方。
        调用方一改，全局模板就跟着脏了，下个任务拿到的就是脏数据。
        所以必须复制一份再给人。

    为什么用 copy.deepcopy 而不是 .copy()？
        .copy() 只复制最外层 —— 里面的 "chunks": [] 还是原来那一个列表，
        改它依然会污染模板。deepcopy 会一层层全部复制成新的，彻底独立。
        一句话：**浅复制只换外壳，深复制连内脏一起换**（§13）。
    """
    return copy.deepcopy(GRAPH_DEFAULT_STATE)
