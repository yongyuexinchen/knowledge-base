# 数据流说明书（FLOW.md）

> 这个文件回答一个问题：**一份文件从进来，到进数据库，中间被谁改成了什么样子？**
>
> 代码注释讲"这一行为什么这么写"，`CONCEPTS.md` 讲"这是什么概念"，
> 本文件讲"**数据怎么流**"。三个文件分工不同，别搞混。

---

## 一、先搞懂：整个项目的数据只有一份

叫 **state**（状态），就是一个大字典。定义在 `processor/import_processor/state.py`。

```
初始状态（11 个字段，全是空的）
        │
        ▼
   ┌─────────┐
   │ NodeEntry│  只改 2 个开关字段，其余 9 个原样不动
   └─────────┘
        │  返回 {"is_md_read_enabled": True, "is_pdf_read_enabled": False}
        ▼
   LangGraph 把这个局部字典**合并**进大 state
        │
        ▼
   ┌───────────┐
   │ NodePDFToMD│  拿到的是"合并后的完整 state"
   └───────────┘
        │  ... 一路往下
        ▼
   最终 state（11 个字段，大部分有值了）
```

**三句话记住机制**：

1. 每个节点拿到的都是**完整的大 state**（LangGraph 帮你合并好了）。
2. 每个节点**只返回自己改动的字段**（局部字典），不是整个 state。
3. 没被提到的字段**保持原值不动** —— 这叫**增量合并**（见 `CONCEPTS.md` §14）。

---

## 二、8 个节点：谁读什么、写什么

> 这是本文件最有用的一张表。**左边的字段从哪来、右边的字段到哪去**，一眼看清。

| # | 节点类名 | 文件 | 读 state 里这些字段 | 写 state 里这些字段 | 加工动作 |
|---|---|---|---|---|---|
| ① | `NodeEntry` | `node_enrty.py` | `import_file_path` | `is_md_read_enabled`<br>`is_pdf_read_enabled` | 看文件后缀，点亮一个开关 |
| ② | `NodePDFToMD` | `node_pdf_to_md.py` | `import_file_path` | `md_path`<br>`file_dir`<br>`file_title` | MinerU 把 PDF 解析成 Markdown，落盘，只存路径 |
| ③ | `NodeMDImg` | `node_md_img.py` | `md_path`（或 `md_content`） | `md_content` | 找图片引用 → 调 VL 模型描述 → 描述回填进正文 |
| ④ | `NodeDocumentSplit` | `node_document_split.py` | `md_content` | `chunks` | 按标题 + 长度切分成若干小块 |
| ⑤ | `NodeItemNameRecognition` | `node_item_name_recognition.py` | `chunks`（取前 3 个） | `item_name` | 调 LLM 归纳"这篇讲的是什么品种" |
| ⑥ | `NodeBGEEmbedding` | `node_bge_embedding.py` | `chunks` | `chunks`（每个多一个向量键） | BGE-M3 把每块文本转成向量 |
| ⑦ | `NodeImportMilvus` | `node_import_milvus.py` | `chunks`<br>`item_name`<br>`task_id` | 基本不改 state | 写 Milvus + MinIO + MongoDB 三个库 |

**图里的分支**（第 ①②步之间）：

```
                    ┌── 是 .pdf ──▶ ② NodePDFToMD ──┐
NodeEntry ①         │                                ├──▶ ③ NodeMDImg
（点开关）           └── 是 .md  ──────────────────────┘
                                （跳过 ②）
```

`NodeEntry` 只负责**点开关**，真正决定走哪条路的是 LangGraph 的**条件边**
（读 `is_pdf_read_enabled` / `is_md_read_enabled` 这两个值来选分支）。

---

## 三、字段流向总表：每个字段的一生

| 字段 | 类型 | 谁**第一次**写入 | 之后谁读 | 什么时候才有值 |
|---|---|---|---|---|
| `import_file_path` | str | **外部调用方**（不是任何节点） | ① `NodeEntry`、② `NodePDFToMD` | 一开始就有 |
| `task_id` | str | 外部调用方（或第 ⑦ 步补上） | ⑦ `NodeImportMilvus` | 一开始就有，可能是空串 |
| `is_md_read_enabled` | bool | ① `NodeEntry` | **路由函数 / 条件边**（不是节点） | ① 跑完之后 |
| `is_pdf_read_enabled` | bool | ① `NodeEntry` | 同上 | ① 跑完之后 |
| `pdf_path` | str | ② `NodePDFToMD`（规划中） | ③ `NodeMDImg` | PDF 分支跑完之后 |
| `md_path` | str | ② `NodePDFToMD` | ③ `NodeMDImg`、④ `NodeDocumentSplit` | ② 跑完之后 |
| `file_dir` | str | ② `NodePDFToMD` | ③（图片往哪存） | ② 跑完之后 |
| `file_title` | str | ② `NodePDFToMD` | ④（当切片元数据） | ② 跑完之后 |
| `md_content` | str | ③ `NodeMDImg` | ④ `NodeDocumentSplit` | ③ 跑完之后 |
| `chunks` | List | ④ `NodeDocumentSplit` | ⑤⑥⑦ | ④ 跑完之后 |
| `item_name` | str | ⑤ `NodeItemNameRecognition` | ⑦ `NodeImportMilvus` | ⑤ 跑完之后 |

**看图记住这个"接力"顺序**（箭头 = 上面那个字段是有下游的）：

```
import_file_path ──▶ [①] ──▶ is_pdf/is_md_read_enabled ──▶ 决定走哪条边
                                                    │
                          ┌─────────────────────────┘
                          ▼
   [②] ──▶ md_path ──▶ [③] ──▶ md_content ──▶ [④] ──▶ chunks ──▶ [⑤] ──▶ item_name
                                                              │              │
                                                              └──────┬───────┘
                                                                     ▼
                                                                    [⑥]
                                                                     │
                                                                     ▼
                                                                    [⑦] 写三个库
```

---

## 四、⚠️ 当前流程里有 3 个"没说清"的地方

这几处不是 bug，是**设计还没定型**，写代码前必须先定下来：

### 1. `md_content` 到底进不进 state？（真矛盾）

- `node_pdf_to_md.py` 的注释说：**MD 内容不要塞进 state**，只存 `md_path`
  （理由是 MD 可能几 MB，会让状态快照变大）
- 但 `node_document_split.py` 读的却是 `state["md_content"]`
- 而 `node_md_img.py` 也要读正文才能找图片引用

**三种可能的解法，选一个**：

| 方案 | 做法 | 代价 |
|---|---|---|
| A. 正文进 state | ③ 把改好的正文写进 `md_content` | 状态变大，但流程最简单 |
| B. 只传路径 | 每个节点自己按 `md_path` 读文件、改完再写回文件 | 省内存，但每步都有磁盘 IO |
| C. 小文件进 state，大文件走路径 | 加个阈值判断 | 最合理但最复杂 |

> 现状代码是"半 A 半 B"——② 想走 B，③④ 假设是 A。**必须先统一**。

### 2. `pdf_path` 没人写

`state.py` 里声明了 `pdf_path`，但 ② 的注释说它只写 `md_path`。
**要么** ② 分两步写两次（先写 `pdf_path` 再写 `md_path`），**要么** 这个字段是多余的。

### 3. 第 ⑥ 步的向量存在哪？

`NodeBGEEmbedding` 把向量"附着"回 `chunks` 里，会让 state 瞬间膨胀
（每个 chunk 多 1024 个浮点数）。chunk 数量少（< 几千）时可以接受，
上量后要考虑"不落 state，直接和 ⑦ 合并成一个节点"。

---

## 五、7 个节点怎么串起来（`graph.py` 还没写）

这是项目**当前最缺的一块**。有了上面那张表，组装逻辑其实很清楚：

```python
# 伪代码，展示"数据流"怎么变成"图"
from langgraph.graph import StateGraph

g = StateGraph(ImportGraphState)          # 告诉框架：数据长这样

g.add_node("entry", NodeEntry())          # 造实例 → 触发 __init__（拿 config + logger）
g.add_node("pdf_to_md", NodePDFToMD())    # 注意：整个程序里每个节点只造一次
g.add_node("md_img", NodeMDImg())
# ...

g.set_entry_point("entry")                # 从哪个节点开始

# 加条件边：① 返回的开关字段决定下一步去哪
g.add_conditional_edges("entry", 路由函数, {...})
g.add_edge("md_img", "document_split")    # 无条件直线
# ...

app = g.compile()
app.invoke(get_default_state() | {"import_file_path": "某文件.pdf"})
#                                ↑ 这就是"外部调用方"给 state 塞初始值的地方
```

**注意 `add_node` 里写的是 `NodeXxx()`（带括号，是个对象）**，
因为节点必须是可调用的——这正是 `BaseNode` 要定义 `__call__` 的原因
（见 `CONCEPTS.md` §5）。

---

## 六、遇到问题时怎么用这份文档

| 现象 | 先查这里 |
|---|---|
| 报 `KeyError: 'xxx'` | 查第二节，看这个字段是**谁**写的、那个节点是不是**排在前面** |
| 某个字段永远是空串 | 查第三节"谁第一次写入"，确认上游节点真的写了 |
| 想加一个新字段 | 先想清楚：谁写、谁读、放哪一步，再动 state.py |
| 改一个节点的逻辑 | 查第二节，确认它**只碰自己那两列**，别去改别人的字段 |
