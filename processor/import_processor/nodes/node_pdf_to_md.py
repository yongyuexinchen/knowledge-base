# processor/import_processor/nodes/node_pdf_to_md.py

from processor.import_processor.base import BaseNode
from processor.import_processor.state import ImportGraphState


class NodePDFToMD(BaseNode):
    """
    PDF 转 Markdown 节点（流水线第 ② 步）：把 PDF 变成纯文本。

    一句话：**吃一个 PDF 文件路径，吐一个 Markdown 文件路径**（不是内容本身）。

    ── 位置 ───────────────────────────────────────────────────────────
    只有入口点亮 is_pdf_read_enabled 时才执行；走 .md 分支会被直接跳过。

    ── 它要干的活 ─────────────────────────────────────────────────────
    不是简单抽文字，而是**还原版面结构**（本项目打算用 MinerU 这个工具）：
        · 识别标题层级 → 输出 # / ## / ###（后面按标题切分就靠它）
        · 识别表格     → 转成 Markdown 表格，保住行列关系
        · 抽离图片     → 存成独立文件，正文里插入 ![](路径) 引用
        · 去掉双栏/页眉页脚 → 否则正文被切碎、噪音混进来
    用 PyPDF2 那种纯文本抽取做不到这些 —— **这一步的质量决定整个 RAG 的上限**。

    ── 开工前要知道的两件事（已实测）──────────────────────────────────
      ① 依赖没装：.venv 里**没有 mineru**。开工前要 uv add "mineru[core]"，
         且 .env 里 MODELSCOPE_OFFLINE=1 意味着模型要提前离线下载好，
         否则第一次跑会报"离线模式下找不到模型"。
      ② 慢：解析几十页 PDF 可能要几分钟。同一份 PDF 重复导入时，
         应先检查产出是否已存在，别每次都重新解析（白烧 GPU 时间）。
    """

    name = "node_pdf_to_md"

    def process(self, state: ImportGraphState):
        """
        调 MinerU 把 PDF 解析成 Markdown，落盘，把路径记进 state。

        输入（从 state 读的字段）：
            import_file_path : str
                哪来的：外部调用方（不是上一个节点写的）
                长什么样："D:/docs/某设备手册.pdf"
                什么时候有值：一开始就有
                怎么用：直接喂给 MinerU 当解析目标

        加工：
            1. 拿 import_file_path 指向的 PDF
            2. 调 MinerU 解析：还原标题/表格/图片
            3. 把 Markdown 正文**写到磁盘**
            4. 图片单独存文件，正文里插入相对路径引用
            5. 从原文件名算出 file_title（去掉扩展名）

        输出：
            建议返回（三个字段）：
                {"md_path": ".../xxx.md",        # MD 文件落在哪
                 "file_dir": ".../xxx/",         # 本次任务的目录（图片也在里面）
                 "file_title": "某设备手册"}      # 原文件名去掉扩展名
            谁接手：
                md_path     → ③ 去这个文件里找图片引用；④ 去读正文
                file_dir    → ③ 图片往哪存
                file_title  → ④ 当切片的来源标签

            ⚠️ 关键设计：MD 内容**不要**塞进 state，只存路径。
               一份 PDF 的 MD 可能几 MB，塞进全程在内存里传递的 state，
               每步快照都会变大，调试时打印 state 直接刷屏。
               **大东西传路径，小数据进 state。**
               ⚠️ 但这与 ③④ 的假设冲突（它们读的是 state["md_content"]）——
                  两种做法必须先定一种，见 docs/FLOW.md 第四节。
        """

        # ⚠️ 目前是空实现：什么都没做就把 state 原样退回，只是占位。
        #    真正跑图时，这个节点会打两行日志（开始啦/完成啦）却毫无产出，
        #    下游拿到的 md_path 是空串，要到切分那步才暴露问题。
        #    建议：实现之前先在这里显式 raise NotImplementedError，
        #         让失败发生在"正确的位置"。
        #
        # ⚠️ 风格不一致：这里返回的是**完整 state**，
        #    而 node_entry 返回的是**只含改动字段的字典**。
        #    统一建议：节点只返回自己改动的字段，例如
        #        return {"md_path": md_path, "file_dir": file_dir, "file_title": title}
        return state
