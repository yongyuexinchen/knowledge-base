# src/knowledge_base/__init__.py
# ================================================================================
# 打包入口说明
#
# ── 这个文件是干什么的？──
# pyproject.toml 里有一行：
#     [project.scripts]
#     knowledge-base = "knowledge_base:main"
# 意思是：项目安装后会生成一个叫 knowledge-base 的命令，
# 执行它 = 调用本文件里的 main() 函数。
# 验证方式（项目根目录下）：
#     uv sync
#     uv run knowledge-base      # 期望输出 Hello from knowledge-base!
#
# ── ⚠️ 一个结构上的问题（知道即可）──
# 真正的业务代码在 processor/ 目录，但它在 src/ **外面**。
# 后果：打包发布时，uv_build 只会收 src/ 下的东西，
#       打出来的包**不含 processor** —— 别人装上会报 No module named 'processor'。
# 现在只在本地跑不受影响；打算 `uv build` 分发前必须先解决
# （把 processor 搬进 src/，或在 pyproject.toml 里声明它也是顶层包）。
# ================================================================================


def main() -> None:
    """
    命令行入口函数（knowledge-base 命令调的就是它）。

    ── 它在流程里的位置 ──────────────────────────────────────────────
    它是整条流水线的**总开关**：将来负责"准备第一份 state → 启动图 → 收尾"。
    目前还没接上，只打印一句问候。

    输入：无参数。将来会从命令行参数拿"要导入的文件路径"，
          也就是 state 里第一个字段 import_file_path 的初始值。

    加工（将来会做三件事）：
        1. setup_logging(logging.INFO)        ← 先打开日志（顺序不能反）
        2. graph = build_import_graph()       ← 把 8 个节点连成图
        3. graph.invoke(get_default_state() | {"import_file_path": 路径})
                        ↑ 空白状态           ↑ 塞入真正的输入

    输出：没有返回值（-> None）。真正的产出是副作用：
          向量/文件/记录被写进三个外部库。

    现在运行 `uv run knowledge-base` 只验证了"打包安装这条链是通的"，
    并没有真正启动导入流水线。
    """
    # 问候语用 print 是合适的：用户敲完命令应该立刻看到反馈。
    # 真正的运行日志才该走 logging（base.py 里的 setup_logging）。
    print("Hello from knowledge-base!")

    # ── 将来这里会长成什么样 ───────────────────────────────────────────
    #     def main() -> None:
    #         setup_logging(logging.INFO)
    #         graph = build_import_graph()          # ← 这个函数目前**还不存在**，
    #         graph.invoke(...)                     #    是项目最缺的一环
    # 写完 graph.py（把 8 个节点连起来），这个项目才算真的能跑。
