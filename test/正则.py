# temp/正则替换测试.py
r"""
熟悉 node_md_img.py 的 _process_md_file 用到的正则替换 API
实验顺序 = 由浅入深，每个实验独立，print 出来对比着看
"""
import re


def show(title, before, after):
    print(f"\n{'=' * 60}\n【{title}】")
    print(f"  替换前: {before!r}")
    print(f"  替换后: {after!r}")


# ----------------------------------------------------------------
# 实验1：最小可用的 sub —— 字符串替换
# sub(新内容, 原文) 返回新字符串，原文本身不变（字符串不可变）
# ----------------------------------------------------------------
text = "价格见 ![desc](images/pic1.png) 请留意"
pattern = re.compile(r"!\[.*?\]\(.*?pic1\.png.*?\)")
new_text = pattern.sub("![一张价格表](http://minio/pic1.png)", text)
show("实验1 基本sub", text, new_text)

# ----------------------------------------------------------------
# 实验2：sub 会替换【所有】匹配处（对比 search 只找第一个）
# 同一张图在正文被引用两次 → 两处一起换
# ----------------------------------------------------------------
text = "开头![desc](a/pic2.png)中间![又提一次](pic2.png)结尾"
pattern = re.compile(r"!\[.*?\]\(.*?pic2\.png.*?\)")
new_text = pattern.sub("【已替换】", text)
show("实验2 sub默认全量替换", text, new_text)

# ----------------------------------------------------------------
# 实验3：只想换第一处？两个办法
# count=1 限制次数；或者用 search 拿位置自己拼（node 项目没用这招）
# ----------------------------------------------------------------
text = "![a](pic3.png)和![b](pic3.png)"
pattern = re.compile(r"!\[.*?\]\(.*?pic3\.png.*?\)")
show("实验3 count=1只换第一个", text, pattern.sub("X", text, count=1))

# ----------------------------------------------------------------
# 实验4：subn —— 顺便拿到"实际替换了几处"
# 这就是修复"共替换N处"日志口径的工具：返回 (新串, 次数)
# ----------------------------------------------------------------
text = "![a](pic4.png) ![b](pic4.png) ![c](pic4.png)"
pattern = re.compile(r"!\[.*?\]\(.*?pic4\.png.*?\)")
new_text, n = pattern.subn("Y", text)
show(f"实验4 subn返回替换次数={n}", text, new_text)

# ----------------------------------------------------------------
# 实验5：lambda 替换者 —— 项目源码里的写法
# 函数收到 Match 对象 m，返回值原样成为替换文本（不做任何二次解释）
# 这里演示：不用 m，直接返回固定串（= node_md_img 的用法）
# ----------------------------------------------------------------
image_file, summary, new_url = "pic5.png", "一张流程示意图", "http://minio/pic5.png"
pattern = re.compile(r"!\[.*?\]\(.*?" + re.escape(image_file) + r".*?\)")
new_text = pattern.sub(lambda m: f"![{summary}]({new_url})",
                       "正文![原描述](images/pic5.png)尾巴")
show("实验5 lambda固定串替换(项目同款)", "![原描述](images/pic5.png)", new_text)

# ----------------------------------------------------------------
# 实验6：lambda 的进阶：按"每处匹配"差异化生成替换内容
# m.group() 是整段匹配，m.span() 是位置 —— 可以用它把"第几次出现"写进去
# ----------------------------------------------------------------
counter = {"n": 0}
def replace_each(m):
    counter["n"] += 1
    return f"![引用{counter['n']}号](url)"
text = "![x](pic6.png) ![y](pic6.png)"
pattern = re.compile(r"!\[.*?\]\(.*?pic6\.png.*?\)")
new_text = pattern.sub(replace_each, text)
show("实验6 函数替换者·每处不同", text, new_text)

# ----------------------------------------------------------------
# 实验7：★ 为什么替换串要给函数而不是直接给字符串
# 纯字符串替换时 \1 \g<0> 这类会被当"捕获组引用"解释，内容不可控会炸；
# 函数返回值则 100% 原样使用
# ----------------------------------------------------------------
text = "![x](pic7.png)"
pattern = re.compile(r"!\[(.*?)\]\(.*?pic7\.png.*?\)")   # 注意这次有捕获组

# 危险写法：摘要里恰好像有 \1（比如模型输出了 "\1" 或路径带反斜杠）
bad_summary = r"高温部件\1号警告"
try:
    r1 = pattern.sub(f"!=[{bad_summary}](u)", text, count=0).replace("!=", "!")  # 直接给字符串
except re.error as e:
    r1 = f"报错: {e}"
r2 = pattern.sub(lambda m: f"![{bad_summary}](u)", text)   # 给函数 → 原样
show("实验7 含反斜杠时：字符串会解释/函数不解释", str(r1), str(r2))

# ----------------------------------------------------------------
# 实验8：多张图的循环替换 —— 项目 _process_md_file 的完整缩影
# image_info 字典 → for 循环逐张 compile + sub → 全文被换 N 遍
# ----------------------------------------------------------------
md = ("手册封面![图](images/aaa111.png)第一节"
      "高温警告![图](images/bbb222.png)第二节"
      "搬运姿势![图](images/ccc333.png)"
      "坏图![图](images/ddd444.png)")     # ddd444 故意不在清单里(上传失败)
image_info = {
    "aaa111.png": ("封面条形码", "http://minio/a.jpg"),
    "bbb222.png": ("高温警告图", "http://minio/b.jpg"),
    "ccc333.png": ("搬运姿势图", "http://minio/c.jpg"),
}
for image_file, (summary, new_url) in image_info.items():
    p = re.compile(r"!\[.*?\]\(.*?" + re.escape(image_file) + r".*?\)")
    md = p.sub(lambda m: f"![{summary}]({new_url})", md)

print(f"\n{'=' * 60}\n【实验8 项目完整缩影】多图循环替换结果:")
print(md)
print("→ 观察：前3处换成了URL，ddd444.png 不在清单里 → 本地路径原样残留（死链）")

# ----------------------------------------------------------------
# 实验9（延伸）：把实验8漏网的本地引用扫出来 —— 上次说的 WARNING 清单
# (?!http) 负向前瞻：括号内紧跟的不是 http 的，就是没换干净的
# ----------------------------------------------------------------
leftover = re.findall(r"!\[.*?\]\((?!http)[^)]*\)", md)
print(f"\n{'=' * 60}\n【实验9 负向前瞻查漏】残留本地引用: {leftover}")