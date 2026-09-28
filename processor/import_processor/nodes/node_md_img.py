# processor/import_processor/nodes/node_md_img.py

from processor.import_processor.base import BaseNode
from processor.import_processor.state import ImportGraphState


# 💡 小知识：下面类的说明文字用了 r""" 开头（r = raw，原样字符串）。
#    因为里面要写正则表达式 r'!\[.*?\]\((.*?)\)'，含反斜杠。
#    普通字符串里 \ 是"转义符"，碰到 \[ 这种不认识的组合会报警告。
#    加了 r，所有 \ 都按字面理解。写正则、写 Windows 路径（C:\Users\...）都记得加 r。
class NodeMDImg(BaseNode):
    r"""
    Markdown 图片处理节点（流水线第 ③ 步）：让模型"看懂"图。

    一句话：**把正文里的 ![](图片路径) 引用，换成一段文字描述** ——
    因为后面的切分和向量化只认识文字，不认识图。

    ── 位置 ───────────────────────────────────────────────────────────
    第 ③ 步，是两条支路的汇合点：
        PDF 分支：① → ② → ③
        MD  分支：① →（跳过 ②）→ ③

    ── 为什么要做这一步 ───────────────────────────────────────────────
    一份 PDF 的关键信息常常挂在图表上（流程图、数据曲线）。
    只切文字，这些内容等于凭空消失。

    ── 用到 config 里的三个参数 ───────────────────────────────────────
        img_content_length = 200   给模型描述图片时，附带图片周边文字的长度
                                   （单看图容易认错场景，带上下文才贴题）
        requests_per_minute = 15   调看图模型的频率上限（供应商有限流）
                                   ⚠️ 50 张图要跑 3 分多钟，是耗时大户
        image_extensions           判断扫到的是不是真图片，过滤链接、附件
    """

    name = "node_md_img"

    def process(self, state: ImportGraphState):
        r"""
        扫出正文里的图片引用，逐张调模型生成描述，再把描述写回正文。
        （这段说明文字也带了 r 前缀，因为下面要写正则，含反斜杠。）

        输入（从 state 读的字段）：
            md_content : str
                哪来的：按当前规划是 ② 产出的正文
                       ⚠️ 但 ② 的注释说"只存路径不存内容"，两种做法冲突，
                          必须先定一种（见 docs/FLOW.md 第四节）
                长什么样："# 第一章\n\n如图所示：![](images/fig1.png)\n\n..."
            或者 md_path : str  ← 如果定的是"只传路径"，就用它去读文件
            file_dir : str      ← 图片文件在哪个目录（② 给的）

        加工：
            1. 用正则扫出所有图片引用：r'!\[.*?\]\((.*?)\)'
            2. 逐个读图（本地路径，或从 MinIO 下载）
            3. 截取图片周边 200 个字符当上下文
            4. 调看图模型（cfg.vl_model）："这张图里画的是什么？"
            5. 把描述**替换**掉原来的图片引用：
                   ![](fig1.png)  →  【图片描述】这是一张收益率曲线……
               为什么是"替换"而不是"追加到文末"？
               state 里没有单独的"图片描述"字段，说明设计就是就地替换；
               好处是切分时描述会落在图片原来的位置，上下文连贯。
            6. 顺便把图片上传 MinIO，正文里的路径换成对象 key

        输出：
            建议返回：{"md_content": 改好的正文}
            谁接手：④ —— 它切分用的就是 md_content
            ⚠️ 目前返回的是完整 state，和"只返回改动字段"的约定不一致。

        副作用（三件要知道的事）：
            ① 会往 MinIO 上传图片（或往 file_dir 写文件）
            ② 会调外部付费 API，有频率限制
            ③ 这一步不做的话，"images/xxx.png" 这种本地临时路径会残留在
               正文里，切分后全是死链 —— 检索命中了也没法展示图片。
        """

        # ⚠️ 空实现占位。
        # 期待的实现骨架：
        #     md = state["md_content"]
        #     for img_ref in re.findall(r'!\[.*?\]\((.*?)\)', md):
        #         desc = call_vl_model(img_ref, context, self.config)
        #         md = md.replace(f"![]({img_ref})", f"【图片描述】{desc}")
        #     return {"md_content": md}     # ← 只返回自己改动的字段
        return state
