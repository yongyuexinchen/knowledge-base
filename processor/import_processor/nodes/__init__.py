# processor/import_processor/nodes/__init__.py
# ================================================================================
# 空文件，作用：让 nodes 成为一个包（原因见 processor/__init__.py）。
#
# ── 8 个节点的顺序和分工（读什么 → 写什么）───────────────────────────────────
#
#   顺序  文件                          从 state 读              往 state 写
#   ──── ──────────────────────────── ──────────────────────── ──────────────────────
#    ①   node_enrty.py                 import_file_path          两个分支开关
#        （文件名拼错了，应为 entry）
#    ②   node_pdf_to_md.py             import_file_path          md_path / file_dir / file_title
#        （仅 PDF 分支经过）
#    ③   node_md_img.py                md_path（或 md_content）   md_content
#    ④   node_document_split.py        md_content                chunks
#    ⑤   node_item_name_recognition.py chunks（前 3 个）           item_name
#    ⑥   node_bge_embedding.py         chunks                    chunks（每段多一个向量键）
#    ⑦   node_import_milvus.py         chunks / item_name        基本不改 state
#                                      / task_id                 （写外部三个库）
#    ─   node_test.py                  不用 state                返回 {}（试验田，不是业务节点）
#
#   完整数据流向 → docs/FLOW.md
#
# ── 一个要留意的坑 ───────────────────────────────────────────────────────────
# 因为这个文件是空的，下面这种写法**会失败**：
#     from processor.import_processor.nodes import NodeEntry   # ❌ 报错
# 原因：NodeEntry 定义在 node_enrty.py 这个**子文件**里，
#       包不会自动把子文件里的名字"摊"上来。
# 正确写法（写全路径）：
#     from processor.import_processor.nodes.node_enrty import NodeEntry   # ✅
# ================================================================================
