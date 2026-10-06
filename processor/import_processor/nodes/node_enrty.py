# processor/import_processor/nodes/node_enrty.py
# ⚠️ 文件名拼错了：entry（入口）被写成了 enrty。
#    类名 NodeEntry 是对的。建议把文件重命名为 node_entry.py
#    （IDE 里 Shift+F6 会自动改所有引用），否则以后按名字找文件会踩空。
import json
import logging
from pathlib import Path

from processor.import_processor.base import BaseNode, setup_logging
from processor.import_processor.exceptions import ValidationError, StateFieldError, FileProcessingError
from processor.import_processor.state import ImportGraphState


class NodeEntry(BaseNode):
    """
    入口节点（流水线第 ① 步）：看文件后缀，点亮一个开关。

    一句话：**判断输入是 .pdf 还是 .md，把判断结果写成两个开关字段。**
    它不加工任何文件内容 —— 只做判断。

    ── 它在流水线里的位置 ─────────────────────────────────────────────
        ① NodeEntry  ← 你在这里（唯一的分岔口）
        ② NodePDFToMD（只有 PDF 分支才经过）
        ③ NodeMDImg → ④ NodeDocumentSplit → ⑤ → ⑥ → ⑦

    ── 为什么用"开关字段"而不是直接说"下一步去哪"？──────────────────────
    节点之间不能直接对话，只能靠改 state 来传话。
    所以：节点把判断结果写进 state → LangGraph 的路由函数读出来 → 决定下一步。
    这样以后加新格式（比如 .docx），只需多加一个开关，入口节点本身不用大改。
    """

    # 覆盖父类默认值 "base_node"。这个名字会用在：
    #   ① 日志工具名 → "import.node_entry"
    #   ② 日志文本   → "--- node_entry 开始啦 ---"
    #   ③ 报错时告诉你哪个节点挂了
    name = "node_entry"

    def process(self, state: ImportGraphState):
        """
        看文件后缀，决定走 PDF 分支还是 MD 分支。

        输入（从 state 读的字段）：
            import_file_path : str
                哪来的：外部调用方塞进来的（不是任何节点写的）
                长什么样："D:/docs/某设备手册.pdf"
                什么时候有值：一开始就有 —— 这是整条流水线的输入本身
            其余 10 个字段本节点一个都不读（此刻它们还都是空值）。

        加工：
            1. 从 import_file_path 取出扩展名
            2. 判断是 .pdf 还是 .md
            3. 把结果写成两个开关
            ⚠️ 只判断，不碰文件本身。

        输出：
            返回 {"is_md_read_enabled": True, "is_pdf_read_enabled": False}
            谁接手：**不是某个节点，而是 LangGraph 的路由函数**：
                is_pdf_read_enabled=True  → 下一步去 ② 做 PDF 转换
                is_md_read_enabled=True   → 跳过 ②，直接去 ③
                两个都是 False            → 格式不支持，报错中止
        """
        # ── 待实现的业务逻辑 ─────────────────────────────────────────────
        # 完整实现大体长这样（供参考）：
        #     from pathlib import Path
        #     suffix = Path(state["import_file_path"]).suffix.lower()
        #     if suffix == ".pdf":
        #         return {"is_pdf_read_enabled": True, "is_md_read_enabled": False}
        #     elif suffix == ".md":
        #         return {"is_md_read_enabled": True, "is_pdf_read_enabled": False}
        #     else:
        #         raise ValidationError(...)   # 不支持的格式要显式报错，别静默放过
        #
        # 用 pathlib 而不是 字符串.split(".")[-1]，因为：
        #   · 不用手工处理 Windows\ 和 Linux/ 的路径分隔符差异
        #   · 天然处理 "a.b.pdf" 这种带多个点的文件名（split 会取错）

        # ── 被注释掉的两种返回（备课用，保留）─────────────────────────────
        # 【方案 A】走 PDF 分支
        # return {
        #     "is_md_read_enabled": False,
        #     "is_pdf_read_enabled": True
        # }
        # 【方案 C】两个都关 —— 会走到"格式不支持"的中止分支
        # return {
        #     "is_md_read_enabled": False,
        #     "is_pdf_read_enabled": False
        # }

        # 【方案 B】走 MD 分支（当前实际生效的就是这个，写死的）
        # ── 为什么只返回这两个字段，其余字段不用管？───────────────────────
        # 这是 LangGraph 的关键规则：**节点返回什么，就只更新什么**。
        # 返回的字典会被合并进总 state，没提到的字段保持原值不动。
        # 所以不用（也不应该）把整个 state 复制一遍再改两个键。
        import_file_path = state.get("import_file_path")
        # import_file_path = state["import_file_path"] #这样写的话字段不存在直接报错
        # 判断路径是否为空
        if not import_file_path:
            raise  StateFieldError(field_name='import_file_path',expected_type=str)

        # 2. 转换Path标准化对象
        import_file_path_obj = Path(import_file_path)
        # 判断文件是否存在
        if not import_file_path_obj.exists():
            raise FileProcessingError(message=f"文件{import_file_path_obj.name}不存在")

        if import_file_path_obj.suffix == ".pdf":
            state["is_pdf_read_enabled"] = True
            state["pdf_path"] = import_file_path
        elif import_file_path_obj.suffix == ".md":
            state["is_md_read_enabled"] = True
            state["md_path"] = import_file_path
        else:
            raise  ValidationError(message=f"该文件的后缀格式{import_file_path_obj.suffix}不支持")
        # 4. 获取上传文件的标题，更新到state中
        state["file_title"] = import_file_path_obj.stem

        # 5. 返回state
        return state


        return {
            "is_md_read_enabled": True,    # 点亮"读 MD"开关 → 路由会跳过 PDF 转换
            "is_pdf_read_enabled": False   # 熄灭 PDF 开关
        }

        # 【方案 D】原样返回整个 state —— 为什么不推荐？
        # return state
        #   1. 浪费：整个字典原样传回，合并时等于全量覆盖一遍，白做工。
        #   2. 有隐患：如果节点里往 state["chunks"] 这类列表塞过东西，
        #      因为列表是"同一个对象"，在返回之前总 state 就已经被改了。
        #      中途一出错，就留下一份"改了一半"的脏数据，还查不出是谁改的。
        # 结论：节点只返回**自己负责改动的字段**，边界清楚、好排查。


