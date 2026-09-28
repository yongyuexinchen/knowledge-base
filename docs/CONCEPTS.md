# 零基础概念手册 —— 给 knowledge_base 项目

> 这份文档解决一个问题：**读代码时遇到看不懂的名词，上哪查。**
>
> 规则：代码里的注释只回答"**这一行为什么这么写**"；凡是"**这个东西是什么、为什么需要它**"，
> 一律来这份文档查。两者不混在一起。
>
> 每个概念固定回答你的六个问题：
> 1. 一句话人话 2. 它在做什么 3. 不做会怎么样 4. 生活类比 5. 替代方案 6. 优化空间

## 阅读建议

不用从头读。按下面这张表跳转 —— 你卡在哪，就查哪一条。

| 你可能想搞懂 | 查第几节 | 对应文件 |
|---|---|---|
| 类和对象到底是什么 | §1 | 全部 |
| `class A(B)` 那个括号什么意思 | §2 | 所有节点 |
| 抽象类、ABC、为什么要有个"不能用的类" | §3 | `base.py` |
| `@abstractmethod` 是干嘛的 | §4 | `base.py` |
| `@` 这个符号是什么原理、怎么自己写装饰器 | §4.1 | 全局 |
| `@abstractmethod` 到底管什么、不管什么 | §4.2 | `base.py` |
| 只继承 ABC、忘了写 `@abstractmethod` 会怎样 | §4.2 | `base.py` |
| 到底谁在"校验"、元类是什么、`__new__` 干嘛的 | §4.3 | `base.py` |
| 为什么业务写 `process`、入口却在 `__call__` | §5 | `base.py` |
| `__init__` 和 `__call__` 老分不清 | §5.1 | `base.py` |
| `def f(self, x: T) -> T:` 每个符号啥意思 | §5.2 | 全局 |
| `@classmethod` 的 `cls` 和 `self` 有啥区别 | §6 | `config.py` |
| `@dataclass` 帮我省了什么 | §7 | `config.py` |
| `total=False`、TypedDict 是什么 | §8 | `state.py` |
| 为什么不用一堆函数、非要用类 | §9 | 全局 |
| 为什么配置要集中、单例是啥 | §10 | `config.py` |
| 为什么要自己定义异常类 | §11 | `exceptions.py` |
| "依赖注入"听着很高级 | §12 | `base.py` |
| 深拷贝浅拷贝，为啥非得 deepcopy | §13 | `state.py` |
| 节点返回半个字典，剩下的字段去哪了 | §14 | `node_enrty.py` |
| 日志怎么就有颜色了、logger 名怎么来的 | §15 | `base.py`、`node_test.py` |
| "日志器"到底是个什么东西、身上有啥 | §15 | `base.py` |
| 一条日志从写出到显示，中间走了哪几步 | §15.0 | `base.py` |
| 为什么打了日志却没输出、格式还变成裸的了 | §15.0 | `base.py` |
| 四个"器"的先后顺序、Filter 插在哪一步 | §15.1 | `base.py` |
| 想"只让某个节点的日志进文件"该怎么做 | §15.1 | `base.py` |
| 按名字前缀筛日志、点号怎么算、下划线为什么不行 | §15.1 | `base.py` |
| 日志名里的 `node_xxx` 是哪来的、`self.name` 怎么找到的 | §15.2 | `base.py`、`nodes/` |
| 为什么日志前缀叫 `import`、怎么一句话管住全部节点 | §15.2 | `base.py` |
| 类型标注 `T`、`-> T` 到底是什么 | §16 | `base.py` |

---

## §1 类与对象

**一句话人话**：类是"图纸"，对象是按图纸造出来的"实物"。

**它在做什么**

```python
class NodePDFToMD(BaseNode):   # ← 这是图纸，此时内存里还没有任何"节点"
    name = "node_pdf_to_md"

node = NodePDFToMD()           # ← 这是按图纸造了一个实物
```

**不这么做会怎么样**

你可能会想："我直接写个函数不就行了？"能。但如果项目里有 8 个步骤，每个都要"打日志 → 干正事 → 出错时报错"，用函数写就是这样：

```python
def pdf_to_md(state):
    print("开始")            # 第 1 遍抄
    try:
        ...
    except Exception as e:
        print(f"出错: {e}")  # 第 1 遍抄
    print("结束")

def md_img(state):
    print("开始")            # 第 2 遍抄（一模一样）
    try:
        ...
    except Exception as e:
        print(f"出错: {e}")  # 第 2 遍抄
    print("结束")
# ... 再抄 6 遍
```

**具体坏在哪**：某天你想把 `print` 换成正式的日志库，得改 8 个地方，漏一个就不一致；某天你想在"开始"里加上任务耗时统计，同样要改 8 处。这叫**重复代码**，是所有维护痛苦的源头。

**生活类比**：8 个工人各自凭记忆做同一道工序，你改一次工艺要求就得挨个通知。改成"统一发一本作业手册"（基类）之后，改手册就等于改所有人。

**替代方案**

| 方案 | 优点 | 缺点 | 什么时候用它 |
|---|---|---|---|
| 纯函数 + 复制粘贴 | 上手最快，不用理解类 | 重复代码，改一处要改 N 处 | 只有 1~2 个步骤的小脚本 |
| 函数 + 装饰器 | 也比复制强，不用面向对象 | 装饰器有独立的语法门槛；想给节点加"属性"（如 `name`）不方便 | 步骤之间没有共享状态时 |
| **类 + 继承（本项目）** | 公共代码写一次；每个节点能带自己的属性；扩展只需加子类 | 要先理解类、继承、多态 | **步骤多（≥3）、且共享同一套前后处理逻辑** |

**优化空间**：本项目 8 个节点共享逻辑已经抽好了，没有明显重复。真正可以优化的是——`base.py` 里 `__call__` 的 `try/except` 把**所有**异常都包成了 `ImportProcessError`，将来如果想让"网络超时"自动重试、"配置错误"直接终止，就得靠 `except` 分类型捕获，而不是一把抓。

---

## §2 继承

**一句话人话**：`class 子类(父类)` 的意思是"子类是一种父类，父类有的它全都有，另外还能有自己的"。

**它在做什么**

```python
class BaseNode(ABC):        # 父类：定义了公共能力
    ...

class NodePDFToMD(BaseNode):  # 子类：白拿到 name/config/logger/__call__
    name = "node_pdf_to_md"
    def process(self, state): ...
```

`NodePDFToMD` 里只写了 5 行，但它已经拥有了父类几十行代码带来的能力。

**不这么做会怎么样**

没有继承，`NodePDFToMD` 就得自己写：

```python
class NodePDFToMD:
    def __init__(self):
        self.config = get_config()
        self.logger = logging.getLogger("import.node_pdf_to_md")
    def __call__(self, state):
        try:
            self.logger.info("开始")
            result = self.process(state)
            self.logger.info("结束")
            return result
        except Exception as e:
            raise ImportProcessError(...)
    def process(self, state): ...
```

这段样板代码，**8 个节点就要写 8 遍**。而且这 8 份会慢慢"跑偏"——有人加了耗时统计，有人忘了加异常包装，最后你完全不知道哪个节点行为特殊。

**生活类比**：继承 = 手机厂商的"模具"。所有型号共用一套主板设计（父类），你要出新型号只需要改外壳和摄像头（子类覆盖 `process`），不用重新发明主板。

**替代方案**

| 方案 | 优点 | 缺点 | 什么时候用它 |
|---|---|---|---|
| 复制粘贴 | 直观 | 8 份副本会各自跑偏（见上） | 只用一次、绝不复用 |
| **组合**：把公共逻辑做成一个对象，塞进每个节点 | 不依赖继承，比继承更灵活（可运行时替换） | 每个节点得自己写一行"调用公共对象"的代码，仍有少量重复 | 当"共享的逻辑"可能有好几种变体时 |
| 函数装饰器 | 语法简洁 | 无法让节点"拥有属性"（`node.name` 拿不到） | 逻辑纯装饰性、无需携带状态 |
| **继承（本项目）** | 写一次、8 个节点全受益；新节点零成本接入 | 类层次加深后不易理解 | **共享同一套"前后处理"、且节点是"一种东西"时** ✅ |

**优化空间**：本项目继承只有两层（`BaseNode` → 各节点），很浅，完全够用。**不要**为此引入更多层继承——三层以上的继承链是公认的维护噩梦。真要扩展，优先用"组合"。

---

## §3 抽象类（ABC）

**一句话人话**：抽象类是一个**故意不让你直接用**的类——它只是个模具，必须由别人继承并补全之后才能用。

**它在做什么**

```python
from abc import ABC, abstractmethod

class BaseNode(ABC):        # 继承 ABC → 变成抽象类
    ...
```

`ABC` = Abstract Base Class，是 Python 标准库里**专门用来做抽象类的工具**。

变成抽象类之后，会有两条硬约束：
1. `BaseNode()` 直接调用 → 报错 `TypeError`
2. 只有当子类把 `process()` 实现了，`NodePDFToMD()` 才能造得出来

**不这么做会怎么样**

不用 `ABC`，父类也能定义 `process`，但**没有任何保护**：

```python
class BaseNode:                      # 没有 ABC
    def process(self, state):
        pass                         # 空壳，不报错

class NodePDFToMD(BaseNode):
    def proccess(self, state):       # ← 拼错了！proccess 多了一个 c
        return state

node = NodePDFToMD()                 # 不报错，正常造出对象
node({"a": 1})                       # 不报错，"开始啦/完成啦"日志照打
```

**具体坏在哪**：你可以想象跑了 3 分钟的 PDF 解析，日志显示"`node_pdf_to_md` 完成啦"，但结果里 `md_path` 还是空的。查半天才发现——`process` 拼错了，父类的空壳 `process` 被调用，什么都没干。**错误现场离真正的原因隔了十万八千里**，这是最难查的一类 bug。

用 `ABC` 之后，错误提前到"造对象"那一行，一眼就看到：

```
TypeError: Can't instantiate abstract class NodePDFToMD
           without an implementation for abstract method 'process'
```

**生活类比**：抽象类 = **合同模板上的空白处**。合同模板你不会直接拿去用（因为关键条款是空的），必须填完才能签字。`ABC` 就是把"没填完就不给签"这件事变成强制规则。

**替代方案**

| 方案 | 优点 | 缺点 | 什么时候用它 |
|---|---|---|---|
| **什么都不做**（普通父类） | 零成本 | 拼错方法名不会报错，错误延后到运行时（见上） | 父类方法有默认实现、且"不覆盖也能跑"时 |
| 只用文档/注释写明"必须实现 process" | 不用学 ABC | 靠自觉，等于没有约束。团队越大越靠不住 | 单人小脚本 |
| **`ABC` + `@abstractmethod`（本项目）** | 运行期强制，错误提前到造对象时；IDE 也会标红 | 多一层语法要理解 | **基类定义了"必须实现的接口"时** ✅ |
| 用 `Protocol`（typing） | 不要求继承，只要"长得像"就行（结构化类型） | 只在静态检查时生效，运行时**不报错** | 想给第三方类套接口、又改不了它源码时 |
| 用 `NotImplementedError` 手写 | 最土但有效 | 要等真跑到那一行才抛错，不如 ABC 早 | 不想用 ABC 时的折中 |

**优化空间**：
- 当前项目已经用了 ABC，很好，不用改。
- 唯一可加的是：给 `process` 加更明确的返回值约束。现在已经能靠 ABC 保证"必须有 process"，但没法保证"必须返回 dict"——那需要 `Protocol` 或运行期校验。
- ⚠️ 注意：`ABC` 的检查**只在"造对象"那一刻做**。它管不了参数对不对、返回值对不对。

---

## §4 `@abstractmethod` 与模板方法模式

**一句话人话**：`@abstractmethod` 给方法盖一个"这里必须填"的章；配上父类写好的流程骨架，就叫"模板方法模式"。

**它在这里是干什么的**

```python
@abstractmethod
def process(self, state: T) -> T:
    pass
```

这一行写了三件事：
1. **声明这是一个必须被实现的方法**（"坑"）
2. 因为类里存在这样的方法，`BaseNode` 自动变成"不能实例化"
3. 谁继承谁就得填，不填就造不出对象

而"模板方法模式"指的是这个结构：

```python
def __call__(self, state):
    self.logger.info("开始啦")       # ← 父类写死的第 1 步
    result = self.process(state)     # ← 第 2 步：留白，子类填
    self.logger.info("完成啦")       # ← 父类写死的第 3 步
    return result
```

**父类钉死流程，子类只填中间的肉。** 这就是"模板"的含义。

**不这么做会怎么样**

1. 如果不加 `@abstractmethod`：见 §3，拼错方法名不会报错。
2. 如果不用"模板方法"、让子类自己写 `__call__`：就回到了 §2 里"8 份样板会跑偏"的问题——有人忘了打日志、有人漏了异常包装，节点行为不一致。

**生活类比**：快餐店的**流​水线**。总部规定动作是"放面包 → 【你放肉和菜】→ 盖面包"。第 2 步各店不同（牛肉/鸡排），但第 1、3 步必须统一。这样不管哪家店，出来的都是汉堡形状，不会有人直接给你一块生肉。

**替代方案**

| 方案 | 优点 | 缺点 | 什么时候用它 |
|---|---|---|---|
| **模板方法（本项目）** | 流程统一，子类只关注业务 | 流程被写死，子类想改顺序只能重写父类方法 | 流程稳定、只中间一步有变化 |
| 挂"钩子方法"：父类流程里再留可选空方法（如 `before()` / `after()`） | 比模板方法更灵活 | 类变复杂 | 需要在流程里插入多个可选扩展点时 |
| 事件回调 / 中间件 | 完全解耦 | 抽象层次更高，调试更难 | 框架级设计 |
| 直接写 8 个独立函数 | 简单 | 见 §2 | 只跑一次 |

**优化空间**：`base.py` 的注释里你自己写了"未来可以在父类的 `__call__` 里实现任务追踪"——**这个想法完全正确**，而且正是模板方法最典型的用法。具体做法：

```python
def __call__(self, state):
    start = time.time()                      # 新增
    self.logger.info(f"--- {self.name} 开始啦 ---")
    try:
        result = self.process(state)
        self.logger.info(f"--- {self.name} 完成啦（耗时 {time.time()-start:.2f}s）---")
        return result
    except Exception as e:
        ...
```

改一处，8 个节点全部获得耗时统计 —— 这就是模板方法的威力。

### §4.1 先搞清楚 `@` 是什么：装饰器

**一句话人话**：`@xxx` 写在函数上方，是「**把这个函数交给 `xxx` 处理一下，再用处理结果替换原函数名**」的简写。

**它在做什么**

```python
@my_deco
def say_hi():
    ...
```

完全等价于：

```python
def say_hi():
    ...
say_hi = my_deco(say_hi)      # 手动装，效果一模一样
```

**实测（本机 `.venv` 验证）** —— 自己写一个装饰器：

```python
def my_deco(func):
    print("装饰器运行，收到函数:", func.__name__)     # ← 注意这行什么时候打印
    def wrapper(*a, **kw):
        print("调用前做点事")
        r = func(*a, **kw)
        print("调用后做点事")
        return r
    return wrapper

@my_deco
def say_hi():
    print("(原函数体执行)")

say_hi()
```

输出：

```
装饰器运行，收到函数: say_hi      ← 这行在最前面！
调用前做点事
(原函数体执行)
调用后做点事
```

第一行排在最前，说明**装饰器在「定义函数」那一刻就执行了**，不是等你调用 `say_hi()` 时才跑。

**三步**：

1. `my_deco` 收到原来的函数 `say_hi`
2. 它返回一个新函数 `wrapper` —— 里面包着原函数
3. 名字 `say_hi` 被重新指向 `wrapper`

→ 之后你调 `say_hi()`，实际跑的是 `wrapper`；`wrapper` 在里面再调原函数。

**你在 Flask 里天天用这个**：`@app.route("/")` 就是"把下面这个函数注册进路由表，并返回一个包装版本"。原理完全一样。

**生活类比**：装饰器像**给快递加一层外包装**。里面的东西没动，但外面多了一层，别人拿到的是包好的那一份。

**替代方案**

| 方案 | 优点 | 缺点 | 什么时候用它 |
|---|---|---|---|
| **`@deco`（语法糖）** | 简短；一眼看出"这个函数被增强了" | 隐藏了调用过程，初学容易懵 | 几乎总是 ✅ |
| 手动 `f = deco(f)` | 过程全显式，好理解 | 冗长；容易漏写 | 研究原理、动态包装时 |
| 在函数体里手写重复逻辑 | 最直白 | 每个函数抄一遍 | 只有 1~2 处时 |

**坑**：

1. `wrapper` 会**丢掉原函数的名字和文档**（`say_hi.__name__` 会变成 `"wrapper"`）。修法是给 `wrapper` 加上 `@functools.wraps(func)`。
2. 装饰器是**在 import 模块时执行**的，不是调用时。所以装饰器里写 `print` 或发网络请求，import 一下就会触发。

### §4.2 `@abstractmethod` 和普通装饰器不一样：它只盖章

上一节的 `my_deco` 返回的是**新函数** `wrapper`。但 `@abstractmethod` **不包装**，实测：

```python
def f(self): pass
print(getattr(f, "__isabstractmethod__", False))   # → False
g = abstractmethod(f)
print(g.__isabstractmethod__)                      # → True
print(g is f)                                      # → True   ← 还是同一个对象！
```

结论：它做的全部事情就是给函数贴一个属性 `__isabstractmethod__ = True`。函数体、参数、名字，一个字都没改。

**那真正拦你的是谁？** 是 **`ABCMeta`**（`ABC` 背后的元类，§3 讲过 ABC）。它在**创建类**的时候扫描所有方法上的这个标记，把"盖了章又没被子类覆盖"的方法名收进 `__abstractmethods__` 这个集合。集合非空 → 禁止实例化。

但"禁止"这个动作**具体发生在哪一层、由谁执行**，这一节说得还不够准 —— 下一节 §4.3 把它拆到底。

实测：

```python
class Base(ABC):
    @abstractmethod
    def process(self, state): pass

Base.__abstractmethods__        # → frozenset({'process'})

class Good(Base):
    def process(self, state): return {"ok": 1}
Good.__abstractmethods__        # → frozenset()       空集合 → 允许创建

class Bad(Base):
    pass
Bad()                           # → TypeError: Can't instantiate abstract class Bad
                                #   without an implementation for abstract method 'process'
```

**它管什么、不管什么（实测边界）**

| 子类的情况 | 创建对象时 | 说明 |
|---|---|---|
| 老老实实实现 `process` | ✅ 成功 | |
| 完全不写 `process` | ❌ TypeError | |
| 名字拼错（`proccess` 多一个 c） | ❌ TypeError | **拼错 = 没实现** ← 这是它最有价值的一条 |
| 写了 `process` 但参数少一个 | ✅ **创建成功！** | 它不检查签名 |

最后一行实测：

```python
class WrongSig(Base):
    def process(self):             # 少了一个 state 参数
        return {}

w = WrongSig()                     # 竟然能创建成功
w.process({"a": 1})                # 到真调用时才报：
                                   # TypeError: WrongSig.process() takes 1
                                   # positional argument but 2 were given
```

而且这个报错是 **Python 普通的函数调用规则**报的，跟 `@abstractmethod` 毫无关系。

**⚠️ 补一个最容易踩的坑：`ABC` 和 `@abstractmethod` 是【两个独立的开关】**

实测三种写法，子类都把 `process` 拼错成 `proccess`：

| 写法 | 结果 |
|---|---|
| `class X:` + `def process: pass` | 静默返回 `None`，**不报错** |
| `class X(ABC):` + `def process: pass`（**忘盖章**） | 还是静默返回 `None`，**不报错** |
| `class X(ABC):` + `@abstractmethod`（本项目） | 造对象时 `TypeError` |

第二种写法实测：

```python
class HalfABC(ABC):
    def process(self, state):        # 有 def，但没贴 @abstractmethod
        pass

HalfABC.__abstractmethods__      # → frozenset()   ← 空的！
HalfChild.__abstractmethods__    # → frozenset()
HalfChild()                      # 能创建
HalfChild().process({"doc": 1})  # → None          静默失败
```

原因：`__abstractmethods__` 这份清单**只统计"盖过章"的方法**。继承 `ABC` 只是"请了检查员上岗"，清单上什么都没勾 —— 他手里是一张白纸。

| 开关 | 管什么 |
|---|---|
| `ABC` | 把类的生产者从 `type` 换成 `ABCMeta`（请检查员） |
| `@abstractmethod` | 在某个方法上盖章（清单上勾一笔"这个必须填"） |

**两个都要开，少一个都拦不住。** `class X(ABC)` 单独用等于没加。

→ **一句话记住**：`@abstractmethod` 保证的是「**有没有实现**」，不是「**实现得对不对**」。

---

### §4.3 到底"谁"在校验？—— 元类、`__new__` 和两个时刻

**一句话人话**：**没有任何东西在"校验"。** 真相是：造类的时候算一次"欠账清单"，造对象的时候查一眼抄好的结论。两个不同时刻、两个不同执行者，中间靠一个看不见的标志位传话。

**先补一个基础：类也是对象**

执行完 `class XxxNode(BaseNode): ...` 这一行之后，`XxxNode` **本身也是一个对象**（一个"类对象"）。既然是对象，就有"谁生产了它"的问题。这个生产者叫**元类（metaclass）**。

```python
type(PlainChild)   # → <class 'type'>           普通类由 type 生产
type(BaseNode)     # → <class 'abc.ABCMeta'>    继承 ABC 之后改由 ABCMeta 生产
type(TestNode)     # → <class 'abc.ABCMeta'>    元类会一路传给子类
```

所以 `ABC` 本身没什么神奇的：它只是把"生产者"从 `type` 换成了 `ABCMeta`。`ABCMeta` 比 `type` 多做两件事，分别在两个时刻。

**时机一 · 造类的那一刻（`ABCMeta.__new__`）—— 记账**

自己写一个元类就能看到时序（`__new__` 是元类的"生产"方法，对应实例的 `__init__`）：

```python
class TraceMeta(type):
    def __new__(mcls, name, bases, ns):
        print(f"[造类] 正在生产 {name}")
        return super().__new__(mcls, name, bases, ns)
    def __call__(cls, *a, **kw):
        print(f"[造对象] {cls.__name__}")
        return super().__call__(*a, **kw)

class Traced(metaclass=TraceMeta):
    pass
# 实测输出：[造类] 正在生产 Traced      ← 注意 class 这一行就打印了

t = Traced()
# 实测输出：[造对象] Traced
```

`ABCMeta.__new__` 干的是：扫描这个类（连同它继承来的）所有方法，凡是带 `__isabstractmethod__` 标记、又**没被子类覆盖**的，把方法名收进一个集合：

```python
BaseNode.__abstractmethods__    # → frozenset({'process'})   非空 → 不许实例化
TestNode.__abstractmethods__    # → frozenset()              空   → 允许实例化
```

同时在解释器的 C 层给这个类置上一个内部标志位（含义：「这是个抽象类」）。

**时机二 · 造对象的那一刻（`object.__new__`）—— 查账**

`XxxNode()` 这一行的完整链条是三步：

```
XxxNode()  →  元类.__call__     →  XxxNode.__new__    →  XxxNode.__init__
              (= type.__call__)    (= object.__new__)    填属性
              第 1 步             第 2 步 ← 抛错在这     第 3 步
```

真正抛 `TypeError` 的是**第 2 步的 `object.__new__`**：它读一下第 1 步留下的那个标志位，非空就拒绝分配对象。它**不做任何扫描**。

**三条实测铁证**

**① 绕过元类也没用 —— 拦截点比 `__call__` 更深**

```python
ABCChild()                         # 路径1  → TypeError
type.__call__(ABCChild)            # 路径2 绕过元类的 __call__ → 照样 TypeError
ABCChild.__new__(ABCChild)         # 路径3 绕过整个 __call__ 层 → 照样 TypeError
```

实测 `ABCChild.__new__ is object.__new__ → True`：子类没自己写 `__new__`，用的是最顶端的 `object.__new__`，也就是解释器自己的 C 代码。

**② 手工擦掉清单，立刻就能造对象 —— 证明没有"校验函数"**

```python
ABCChild.__abstractmethods__                  # frozenset({'process'})
ABCChild()                                    # TypeError
ABCChild.__abstractmethods__ = frozenset()    # 手工改成空集合
ABCChild()                                    # 成功了！
ABCChild.__new__(ABCChild)                    # 连直接调 __new__ 都成功了
```

判断依据**就是那个集合**（的镜像标志位）。如果存在一个独立的"校验函数"，改数据是救不活的。

**③ 清单只算一次，之后不会自动更新 —— 证明是"一次性记账"**

```python
class Later(ABCBase):
    pass
Later.__abstractmethods__                     # frozenset({'process'})

Later.process = lambda self, s: {"ok": 1}     # 事后动态补上方法
Later.__abstractmethods__                     # 还是 frozenset({'process'})！没变
Later()                                       # 依然被拦
```

**不做会怎么样**（这是"为什么需要抽象类"的正面回答）

两边都是同一个拼写错误（`process` → `proccess`），实测结果：

| 步骤 | 普通类（无 ABC） | 抽象类（本项目） |
|---|---|---|
| 定义类 | ✅ 无人察觉 | ✅ 记下欠账 |
| 造对象 | ✅ 畅通无阻 | ❌ **TypeError** |
| 跑完整条流水线 | ✅ 日志还照打"完成啦" | 到不了 |
| 下游读 `md_path` | ❌ `AttributeError: 'NoneType' ...` | 到不了 |

普通类那条路的实测细节：

```python
class PlainBase:
    def process(self, state): pass          # 空壳，什么也不干也不报错
class PlainChild(PlainBase):
    def proccess(self, state):              # 拼错：多一个 c
        return {"md_path": "/x.md"}

r = PlainChild().process({"doc": "a"})
print(r)                                    # → None   ← 走了父类那个空壳
r.get("md_path")                            # → AttributeError: 'NoneType'
                                            #   object has no attribute 'get'
```

报错原文说的是"`NoneType` 没有 `get` 方法"，跟"`process` 拼错了一个字母"**看不出任何关系**。

**⚠️ 但这里有个前提，不说清会误导**：普通类之所以"不报错"，是因为**父类留了一个同名的空壳**在做兜底。如果没有空壳，一样会报错：

```python
class BBase:
    def __call__(self, state):
        return self.process(state)    # 父类里根本没有 process 这个方法

class BChild(BBase):
    def proccess(self, state):        # 拼错
        return "我干活了"

BChild()({"doc": 1})
# → AttributeError: 'BChild' object has no attribute 'process'
```

两种情况的实测对照：

| 父类写法 | 子类拼错后 `__call__` 里执行 `self.process(state)` |
|---|---|
| 父类有 `def process(self, state): pass` | 找到空壳 → **返回 None，不报错** |
| 父类没有 `process` | **AttributeError** |

**那本项目为什么一定是第一种？** 因为 `@abstractmethod` 必须贴在**一个真实存在的函数**上。实测 `@abstractmethod process`（不带 `def`）直接 `SyntaxError`。所以想用这个装饰器，就必然要先写下 `def process(...)` —— **空壳是"贴装饰器的副产品"，躲不掉**。

**最本质的一句**：调用方（LangGraph / 父类的 `__call__`）只会喊 `process` 这个名字。子类拼成 `proccess`，等于**注册了一个没人会喊的名字** —— 那个方法真实存在、手动也能调，但永远不会被框架调用。

```python
obj = AChild()                    # 父类留了空壳
obj.proccess({"doc": 1})          # → '我干活了'   能调！但没人会这么调
obj.process({"doc": 1})           # → None         框架用的是这个，落到空壳
```

→ **这才是抽象类真正值钱的地方**：它把错误从"下游某处莫名其妙的 `None`"提前到"造对象那一行"。项目里 6 个存根节点只要有一个漏写或拼错 `process`，在建节点对象的那一刻就会炸，不用等它跑起来。

**两种失败方式真正的差别是"报错时机 + 错误信息清晰度"**：

| | 报错时机 | 错误信息 |
|---|---|---|
| 普通类（父类无空壳） | 跑图时（调用 `__call__`） | `'BChild' object has no attribute 'process'` |
| 普通类（父类有空壳） | **永不报错** | —— 只在很久之后以 `NoneType` 的面目出现 |
| **抽象类** | **造对象时** | `Can't instantiate ... abstract method 'process'` ← 直接点名 |

**生活类比**

| 概念 | 类比 |
|---|---|
| 元类 `ABCMeta` | 制造模具的工厂。普通工厂是 `type`，它多贴一张标签 |
| 时机一（记账） | 模具出厂时贴上"还缺哪些零件"的标签 |
| 时机二（查账） | 提货时 `object.__new__` 这个门卫扫一眼标签，非空就不放行 |
| 门卫的局限 | 它**不看零件质量**，只读标签 —— 所以管不了签名对不对（§4.2） |

**有没有别的做法**

| 方案 | 优点 | 缺点 | 什么时候用 |
|---|---|---|---|
| 什么都不做（普通父类） | 零成本 | 拼错静默，错误延到下游 | 父类方法有真实默认实现 |
| `raise NotImplementedError` | 不用碰元类 | 错误在**调用时**才暴露，比 ABC 晚一步 | 简单脚本 |
| **`ABC` + `@abstractmethod`（本项目）** | 造对象时就拦，错误暴露最早 | 只管名字，不管签名和返回值 | 基类定义"必须实现的接口" |
| `typing.Protocol` | 不用继承，"长得像"就行 | 运行期完全不拦 | 套不了源码的第三方类 |
| 运行时手写 `hasattr` 检查 | 想查什么查什么 | 得自己记得调，容易漏 | 还想顺带检查返回值类型 |

**能优化什么**

1. **管不了签名** —— 想查可以用 `inspect.signature` 对比参数，或者交给 mypy 在静态期查。
2. **清单是缓存，不自动更新** —— 用 `type()` 动态生成节点类时，改完方法要手动重算 `cls.__abstractmethods__`，否则判断是陈旧的（铁证③）。
3. **只管造对象那一刻** —— 对象造出来之后 `process` 被 monkey patch 覆盖，它管不了。
4. **只在 `__new__` 里检查** —— 走非标准路径造实例（如反序列化）时，行为要单独确认。

**本项目里的实际状态（实测）**

```python
BaseNode.__abstractmethods__       # frozenset({'process'})  ← 模具本身，不许直接用
TestNode.__abstractmethods__       # frozenset()             ← 8 个节点都在这变空
NodePDFToMD.__abstractmethods__    # frozenset()

BaseNode.process.__qualname__      # BaseNode.process      (isabstract = True)
NodePDFToMD.process.__qualname__   # NodePDFToMD.process   (isabstract = False)
```

最后两行值得看一眼：**同一个名字 `process`，从哪个类上取就得到哪个类的函数**。基类那个是"模板上的空白"，子类那个才是"真正填进去的内容"。`BaseNode.process` 永远不会被执行 —— 这就是它方法体只有 `pass` 的原因（见 §4.1 尾）。

---

## §5 魔法方法 `__call__`

**一句话人话**：只要类里定义了 `__call__`，这个类的**实例后面跟圆括号时，就会自动执行 `__call__`**。

**它在做什么**

```python
node = NodePDFToMD()      # 造对象
node({...})               # ← 等价于 node.__call__({...})
```

这句 `node({...})` 看着像在调用函数，其实 Python 内部翻译成了 `node.__call__({...})`。

**为什么必须这么写（这是全项目最关键的一个设计决定）**

因为 **LangGraph 把"节点"当成一个函数来调用**。它内部就是这么干的：

```python
# LangGraph 源码里的逻辑（概念示意）
result = node(state)      # ← 必须能这么调用！
```

如果你把业务逻辑放在 `process` 里、却不写 `__call__`，那 `node(state)` 会直接报错 `TypeError: 'NodePDFToMD' object is not callable`。

所以作者的选择是：**`__call__` 专门用来接 LangGraph 的调用，并在里面套上日志和异常包装；`process` 专门给子类填业务。**

**不这么做会怎么样**

| 写法 | 结果 |
|---|---|
| 只写 `process`，不写 `__call__` | `node(state)` 报错，LangGraph 完全跑不起来 |
| 写 `__call__` 但里面**只调 process、不做其他事** | 能跑，但日志和异常包装没了，8 个节点要靠自己维护这些 |
| 业务直接写在 `__call__` 里，子类去重写 `__call__` | 能跑，但子类一重写就把"父类的日志和异常包装"整个覆盖掉了，等于模板方法失效 |

**生活类比**：`__call__` 是把一个"东西"变成"按钮"的开关。一台咖啡机（对象）本来是"东西"，按一下按钮（`__call__`）它才动起来。LangGraph 就是那个只会"按按钮"的人，它不关心咖啡机内部怎么运作。

**替代方案**

| 方案 | 优点 | 缺点 | 什么时候用它 |
|---|---|---|---|
| **`__call__`（本项目）** | LangGraph 零配置就能用；实例本身就是可调用对象 | 语法比较"魔法"，第一次见会懵 | 框架要求"节点可调用"时 ✅ |
| 直接传函数 `workflow.add_node("x", lambda s: ...)` | 最直白 | 拿不到实例属性（`self.config`、`self.logger`），要么闭包要么全局变量 | 无状态的极简节点 |
| 传 `functools.partial(obj.process, ...)` | 不用写 `__call__` | 会绕过父类的日志和异常包装 | 不想要那层包装时 |
| 用 `langgraph` 的 `RunnableLambda` 包一层 | 官方推荐做法之一 | 多一层包装 | 需要和 LangChain 生态混用时 |

**优化空间**：
- 可以在 `__call__` 里加**返回值校验**：如果 `process` 返回了 `None` 或者不是 dict，直接报错。现在如果子类忘了 `return`，`result` 就是 `None`，将来合并进 state 时才会炸，现场很绕。
- `raise ImportProcessError(...)` 建议补成 `raise ... from e`，保住原始异常的完整链条（traceback 会明确显示"上面那个异常是导致这个异常的直接原因"）。

### §5.1 最容易混的一对：`__init__` 和 `__call__`

两个名字长得像，触发时机完全不同 —— **看圆括号左边是谁**：

| 你写的代码 | 圆括号左边 | 触发谁 | 执行次数 |
|---|---|---|---|
| `TestNode()` | **类名** | `__init__` | 一个对象一辈子只跑一次 |
| `node({...})` | **实例名** | `__call__` | 想调几次调几次 |

实测（本机 `.venv` 验证）：

```python
class Trace:
    def __init__(self):
        print("[__init__] 执行 —— 由 类名() 触发")
    def __call__(self, x):
        print("[__call__] 执行 —— 由 实例() 触发，参数 =", x)

t = Trace()   # 打印 [__init__]
t(1)          # 打印 [__call__]
t(2)          # 再打印一次 [__call__]；__init__ 不会重复执行
```

记忆方式：**`__init__` 是"出生"，`__call__` 是"上班"**。出生只有一次，上班可以上很多次。

在你项目里的分工：

```
node = TestNode()        → __init__  → self.config / self.logger 就位
node({"abc": 456})       → __call__  → 打"开始啦" → self.process() → 打"完成啦"
```

### §5.2 签名逐块拆解

```python
def __call__(self, state: T) -> T:
```

| 片段 | 含义 | 备注 |
|---|---|---|
| `def` | 开始定义一个函数（在类里叫方法） | |
| `__call__` | 方法名 | 双下划线是约定：这类名字有特殊含义，**不能自己乱起** |
| `self` | 拿到"正在干活的这个对象自己" | **不用你传**，Python 自动把点号左边那个对象塞进来 |
| `state` | 真正传进来的参数 | 就是你调用时括号里那个状态字典 |
| `: T` | **类型标注** | 见下面第 ② 条 |
| `-> T` | 返回类型标注 | 写给人看的 |
| `:` | 签名结束 | 后面缩进的代码块才是函数体 |

两个补充事实（都实测过）：

**① `self` 不是关键字，只是惯例。** 改叫 `this`、`me` 都能跑。但全世界都写 `self`，别标新立异，否则看别人代码会对不上。

**② 类型标注在运行时完全不被检查。** 实测：

```python
def needs_int(x: int) -> int:
    return x * 2

needs_int("abc")     # 标了 int，传字符串 → 不报错，算出 'abcabc'
```

标了 `int` 却传字符串，Python 不但不拦，还照常算出了结果。**类型标注是给人和类型检查器（mypy / pyright）读的，不是运行时校验。** 这和 §8 的 TypedDict 是同一个道理。

那 `T` 又是什么？见 §16。

---

## §6 `@classmethod` 与 `cls`

**一句话人话**：Python 里"用点号调用"时，**点号左边那个东西会被自动塞进方法的第一个参数**。接住它的参数叫什么，决定了这是个什么方法。

**它在做什么**

```python
class ImportConfig:
    @classmethod
    def from_env(cls):
        return cls()          # ← cls 是"调用它的那个类"
```

四种调用方式，一一对应：

| 写法 | 第一个参数收到什么 | 参数通常叫 | 叫什么方法 |
|---|---|---|---|
| `obj.foo()` | 实例 `obj` | `self` | 普通实例方法 |
| `Cls.foo()`（加 `@classmethod`） | 类 `Cls` | `cls` | 类方法 |
| `obj.foo()`（加 `@classmethod`） | 类 `type(obj)` | `cls` | 类方法（同上） |
| `Cls.foo()`（加 `@staticmethod`） | **什么都不收** | 无 | 静态方法 |

**关键点：`@classmethod` 的价值是"支持继承"**

```python
class TestConfig(ImportConfig):
    debug: bool = True

TestConfig.from_env()     # cls 是 TestConfig → 造出来的是 TestConfig ✅
```

如果 `from_env` 里写死了类名：

```python
    @classmethod
    def from_env(cls):
        return ImportConfig()      # ❌ 写死
```

那 `TestConfig.from_env()` 也会造出一个 `ImportConfig`，子类的 `debug` 字段就丢了。**`test.py` 那个实验验证的就是这件事**（实测输出里 `type(c)` 是 `TestConfig`）。

**不这么做会怎么样**

如果 `from_env` 写成普通实例方法：

```python
    def from_env(self):        # 没有 @classmethod
        return ImportConfig()

ImportConfig.from_env()        # 报错：少传了 self 参数
```

因为用**类**去调实例方法时，`self` 收到的是"类本身"而不是实例——能跑但语义全错，非常容易把人绕晕（详见 `config.py` 里那段注释）。

**生活类比**：`self` 是"我这个人"，`cls` 是"我这家工厂"。`from_env()` 要干的事是"按图纸造一个新配置"，这是**工厂的活**，不是"某个已有配置的活"，所以应该由工厂（`cls`）来干。

**替代方案**

| 方案 | 优点 | 缺点 | 什么时候用它 |
|---|---|---|---|
| **`@classmethod` 工厂（本项目）** | 支持继承，子类自动适配；语义清晰 | 多一个概念 | 需要"从某种来源构造对象"，且要考虑继承 ✅ |
| 直接在 `__init__` 里读环境变量 | 最简单，少写一个方法 | `__init__` 一执行就必然读环境变量，没法"造一个空配置再填"；也不好写测试 | 配置来源唯一且简单时 |
| 模块级函数 `build_config()` | 最直白 | 不支持继承（函数不知道是谁在调） | 不需要继承体系时 |
| `pydantic.BaseSettings` | 自动从环境变量读、自带校验、类型转换 | 引入一个依赖 | 配置项很多、需要严格校验时（**这个项目其实很适合**） |

**优化空间**：本项目 `from_env()` 内部其实只是 `return cls()`（因为读环境变量的逻辑已经写在 `field(default_factory=...)` 里了）。所以 `from_env()` 目前**和 `ImportConfig()` 完全等价**，只是名字更能表达意图。这是合理的，但如果哪天想加"必需的配置项缺失就报错"的校验，`from_env()` 就是最好的落点。

---

## §7 `@dataclass` 与 `field(default_factory=...)`

**一句话人话**：`@dataclass` 让 Python **根据你声明的字段自动生成构造方法**，你不用再手写一堆 `self.x = x`。

**它在做什么**

```python
@dataclass
class ImportConfig:
    max_content_length: int = 2000
```

等价于手写：

```python
class ImportConfig:
    def __init__(self, max_content_length=2000):
        self.max_content_length = max_content_length
    def __repr__(self): ...     # dataclass 还顺手帮你生成了打印格式
    def __eq__(self): ...       # 还有相等比较
```

19 个字段 → 手写约 40 行 `__init__`，`@dataclass` 用 19 行搞定。

**`field(default_factory=...)` 是干什么的**

用来解决一个具体的坑：**可变默认值**。

```python
image_extensions: Set[str] = {".jpg", ".png"}     # ❌ 危险
```

这么写的后果是：这个集合**只在类定义时创建一次**，被所有实例共享。A 实例往里加了 `.svg`，B 实例也会莫名多出 `.svg`。Python 3.11+ 遇到这种写法会**直接报错**，逼你用 `default_factory`：

```python
image_extensions: Set[str] = field(
    default_factory=lambda: {".jpg", ".png"}    # ✅ 每次实例化都新建一个
)
```

`default_factory` 收一个"无参函数"，每次造对象都调用它 → 每个实例拿到独立的集合。

**不这么做会怎么样**

```python
c1 = ImportConfig()
c2 = ImportConfig()
c1.image_extensions.add(".svg")
print(c2.image_extensions)     # 用共享默认值时：{'...', '.svg'} ← 污染了！
```

这类 bug 极其隐蔽：它**不在你改动的那段代码里出问题**，而是跑到另一个毫不相关的对象上才爆炸。可能几个小时后你才发现"为什么 B 对象多了一个我没加过的扩展名"。

**生活类比**：便利店的**一次性纸杯**。每次来客人都拿个新的（`default_factory`）。如果改成"全店共用一个杯子"（可变默认值），那所有客人的饮料都会混在一起。

**替代方案**

| 方案 | 优点 | 缺点 | 什么时候用它 |
|---|---|---|---|
| **`@dataclass` + `default_factory`（本项目）** | 代码量少、自动 `__repr__`/`__eq__` | 没有类型校验、没有环境变量自动读取 | 配置/数据容器类 ✅ |
| 手写 `__init__` | 完全可控 | 19 个字段写 40 行，改字段要同步改签名 | 字段很少（≤3）且逻辑特殊时 |
| `typing.NamedTuple` | 不可变、轻量、可解包 | 不可变（配置里想中途改就不行）；`NamedTuple` 的可变默认值问题更麻烦 | 纯只读的轻量数据 |
| `pydantic.BaseModel` | 自动校验 + 类型转换 + 从环境变量读 | 多一个依赖，性能略低 | **需要严格校验配置合法性时** |
| 普通 `dict` | 最灵活 | 没有自动补全、字段名拼错不报错 | 临时的、结构不固定的数据 |

**优化空间**：
- 本项目 `@dataclass` 用得对。唯一要加的是 `freeze=True` 可以让配置**不可变**，防止某处代码不小心改了全局配置（现在是共享单例，谁来一句 `cfg.embedding_dim = 512` 就污染全程序）。
- 甚至更推荐：把 `ImportConfig` 换成 `pydantic` 版本 —— 现在 `default_model` 那个 `MODEL` / `LLM_DEFAULT_MODEL` 键名不一致的 bug，如果有 pydantic，配上 `validation_alias` 就能一眼看出问题。

---

## §8 TypedDict

**一句话人话**：`TypedDict` 是给字典写"说明书"的——它告诉你的 IDE："这个字典应该有这些字段、这些类型"。**但它运行时什么都不管。**

**它在做什么**

```python
class ImportGraphState(TypedDict):
    task_id: str
    is_md_read_enabled: bool
```

**注意语法**：只有冒号 `:`，没有等号 `=`。因为它不存值，只声明"应该有这个字段"。这和 `@dataclass` 的 `字段名: 类型 = 默认值` 完全不一样 —— 这是最容易搞混的一点。

用它的收益：

```python
state["is_md_read_enaled"]     # IDE 立刻标黄："这个字段不存在"
state["is_md_read_enabled"].     # 打点号时，IDE 弹出 bool 的方法（如 .bit_count()）
```

**不这么做会怎么样**

```python
state = {"task_id": "x"}
state["is_md_read_enabled"]    # KeyError: 'is_md_read_enabled'
```

这行代码照样能写，但只有**真正跑到这一行**才报错。如果它在流程第 5 个节点、需要先跑 3 分钟 PDF 解析才轮到，你就得等 3 分钟才看到这个低级错误。有了 `TypedDict`，IDE 会立刻标黄 —— **把错误从"运行 3 分钟后"提前到"敲代码的那一刻"**。

⚠️ 但要记住 `TypedDict` 的边界：**它纯粹是"给人和工具看的"，运行时完全不校验**。项目里 `node_test.py` 传了 `test_node({"abc": 456})` —— 一个字段都不对的字典 —— 跑起来毫无问题。这证明了这一点。

**生活类比**：`TypedDict` = 表格表头的**填写说明**（"姓名：文本，年龄：数字"）。表格本身还是那张纸，你非要在"年龄"栏写"十七岁"，纸也不拦你——但审核的人（IDE / mypy）会提醒你。

**替代方案**

| 方案 | 优点 | 缺点 | 什么时候用它 |
|---|---|---|---|
| **`TypedDict`（本项目，LangGraph 标配）** | 零运行开销；原生 dict 兼容；LangGraph 天然支持 | 运行时不校验；`total=False` 等细节容易踩坑 | 框架要求传 dict 时的类型标注 ✅ |
| 普通 `dict` | 什么都不用学 | 没补全、拼错不提醒 | 结构完全动态时 |
| `@dataclass` | 有校验、有默认值、可带方法 | LangGraph 想要的是 dict，得额外转换；不能做"部分更新" | 状态字段固定、不需要增量合并时 |
| `pydantic.BaseModel` | 运行期强校验 + 类型转换 | 转 dict 有开销；部分更新语义要自己想 | **状态需要强校验时**（比如外部输入不可信） |

**优化空间**：这是本项目**当前最该修的一处**：

```python
class ImportGraphState(TypedDict):            # 现在：所有字段都必填
class ImportGraphState(TypedDict, total=False) # 建议：所有字段可选
```

或者更精确 —— 只把"逐渐会被填充"的字段标成可选：

```python
from typing import NotRequired

class ImportGraphState(TypedDict):
    task_id: str                    # 必填
    md_path: NotRequired[str]       # 可选：还没生成时不存在
    chunks: NotRequired[List[dict]] # 可选
```

原因：现在 `state.py` 的 docstring 写着"使用 total=False"，但代码里没加；而 `node_enrty.py` 返回的确实是个"只含 2 个字段的局部字典"，在 `total=True` 语义下类型不合法。**文档和代码得统一。**

---

## §9 为什么用类而不是函数（设计取舍）

**一句话人话**：如果 8 个步骤共享同一套"前后处理"和同一份配置，用"类 + 继承"能省掉大量重复；如果没有共享，用函数更好。

**判断标准（可以直接拿去用）**

| 情况 | 推荐 |
|---|---|
| 步骤少（1~2 个） | 函数 |
| 步骤多，但彼此毫无共性 | 各自独立的函数 |
| **步骤多 + 有共同的前后逻辑 + 需要共享配置** | **类 + 继承** ✅（本项目） |
| 步骤多、共性逻辑还会变体 | 类 + 组合（把共性做成可替换的对象） |

**不用类会怎么样（本项目的具体后果）**

假想用纯函数写这个流水线：

```python
def pdf_to_md(state, config): ...
def md_img(state, config): ...
def document_split(state, config): ...
```

1. **配置得层层传递**：每个函数都得带 `config` 参数，调用链一长就烦。
2. **日志得各自初始化**：每个函数开头都要 `logging.getLogger(...)`。
3. **异常处理重复 8 遍**：或者全靠调用方包一层 —— 但那样就分不清是哪个步骤挂的。
4. **没法加通用能力**：想统计每步耗时？8 个函数都要改。

用类之后这四件事全部消失：`self.config` 自动可用、`self.logger` 自动命名、异常包装在父类一处、耗时统计改父类一处。

**替代方案**

| 方案 | 优点 | 缺点 |
|---|---|---|
| **类 + 继承（本项目）** | 上述四点全解决；新节点零成本 | 要先掌握类/继承/抽象类 |
| 函数 + 全局变量存配置 | 简单 | 全局变量是最坏的耦合方式，测试困难 |
| 函数 + 装饰器 | 装饰器能解决"日志/异常/耗时" | 解决不了"共享配置"和"节点带属性" |
| 函数 + 闭包工厂 | 能捕获配置 | 语法晦涩；`functools.wraps`、调试都很麻烦 |

**优化空间**：本项目这个选择是**对的**，不用改。要留意的是别"为了用类而用类" —— 现在 6 个节点还是空壳，如果将来发现某个步骤其实只有 3 行代码、也不需要配置，那它完全可以是一个普通函数，不必硬套 `BaseNode`。

---

## §10 配置收敛与单例

**一句话人话**："配置收敛" = 全项目只有**一个地方**去读环境变量；"单例" = 全程序只造**一个**配置对象。

**它在做什么**

```python
_config = None                       # 模块级私有变量

def get_config():
    global _config
    if _config is None:              # 第一次调用才真正创建
        _config = ImportConfig.from_env()
    return _config                   # 之后都返回同一个对象
```

**为什么必须写 `global`**：函数里对变量**赋值**时，Python 默认认为你要建一个局部变量。不写 `global`，`_config = ...` 只是新建了一个局部变量，模块级那个永远是 `None` —— 单例就失效了。**记忆：只读不用 global，赋值必须 global。**

**不这么做会怎么样**

**（一）不收敛**——环境变量读散了：

```python
# node_pdf_to_md.py
md_root = os.getenv("MD_ROOT_DIR", "./temp")       # 这里
# node_md_img.py
md_root = os.getenv("MD_ROOT_DIR", "./tmp")        # 默认值不一样了！
# api/routes.py
md_root = os.getenv("mD_ROOT_DIR", "./temp")       # 大小写拼错了
```

**具体坏在哪**：三处默认值不一致，文件被写到 `./tmp` 却去 `./temp` 找；第三处键名拼错，永远拿到默认值。这类 bug 不会报错，只会让文件"神秘消失"。收敛到一个文件后，这类问题从根上消失。

**（二）不单例**——每次读都造新对象：

```python
cfg1 = ImportConfig()
cfg2 = ImportConfig()
cfg1.max_content_length = 500
print(cfg2.max_content_length)     # 2000 ← 改了一个，另一个不知道
```

**生活类比**：单例 = 公司**只有一个财务系统**。如果每个部门都自己建一套记账表，季度汇总时数据必然对不上。

**替代方案**

| 方案 | 优点 | 缺点 | 什么时候用它 |
|---|---|---|---|
| **模块级变量 + `global`（本项目）** | 零依赖、直观 | 非线程安全；测试时难以重置（要手动改 `_config = None`） | 单进程脚本 ✅ |
| `functools.lru_cache` 装饰构建函数 | 代码更短，缓存语义天然就是单例 | 同样无法重置 | 同上 |
| 类 + `__new__` 控制 | 显式单例类 | Python 里这么写属于过度设计 | 需要跨模块共享单例类时 |
| 模块级直接创建 `CONFIG = ImportConfig.from_env()` | 最简单，连 `global` 都不用 | **import 时就执行**，读不到还没加载的环境变量 | 配置来源确定时 |
| 依赖注入（每次传参） | 最易测试 | 调用链要传参，啰嗦 | 大型项目 / 需要多套配置并存 |
| `pydantic-settings` | 自动收敛 + 校验 | 多一个依赖 | **配置项多时强烈推荐** |

**优化空间**：
1. **加线程锁**：现在多线程首次同时调用 `get_config()` 可能造出两个对象。单进程流水线暂时无碍，要严谨就加双检锁。
2. **加重置接口**：`def reset_config(): global _config; _config = None`，方便写测试。
3. ⚠️ **`load_dotenv(override=True)` 是生产环境的隐患**：`override=True` 会让 `.env` 里的值**覆盖**系统环境变量。如果服务器上注入的正式密钥和 `.env` 里的测试密钥同名，`.env` 会把正式值顶掉。稳妥做法是本地 `override=True`、生产环境不写或写 `override=False`。

---

## §11 自定义异常

**一句话人话**：把"出错了"这句话，改成"**哪个节点的哪个字段因为什么原因**出错了"。

**它在做什么**

```python
class ImportProcessError(Exception):   # 所有自定义异常的爹
    def __init__(self, message, node_name="", cause=None):
        self.node_name = node_name     # 携带"哪个节点"
        self.cause = cause             # 携带"原始异常"
        super().__init__(message)
```

以及一整套分类：

```
ImportProcessError
├── StateFieldError          状态字段缺失/类型不对
├── ConfigurationError       配置错误
├── FileProcessingError      文件处理错误
│   ├── PdfConversionError   PDF 转换失败（MinerU）
│   └── ImageProcessingError 图片处理失败
├── DocumentSplitError       切分失败
├── EmbeddingError           向量化失败
├── LLMError                 LLM 调用失败
├── StorageError             存储失败
│   ├── MilvusError
│   └── MinioError
└── ValidationError          数据校验失败
```

**不这么做会怎么样**

只用内置异常：

```python
raise ValueError("文件找不到")
```

调用方 `except ValueError` 时，拿到的是"文件找不到"这 5 个字。**是哪个节点的文件？是原始 PDF 还是转换后的 MD？** 全靠猜。

而且更麻烦的是"无法分类处理"：

```python
try:
    run_pipeline()
except Exception as e:
    if "向量" in str(e):        # 😱 靠字符串匹配来判断错误类型
        retry()
    elif "超时" in str(e):
        ...
```

**具体坏在哪**：哪天你把报错文案从"向量化失败"改成"embedding 生成失败"，重试逻辑就静默失效了。靠字符串匹配做控制流，是最脆弱的设计之一。有了分类异常：

```python
except MilvusError:      # 稳定、不会因为改文案而失效
    retry()
```

**生活类比**：医院分诊。只说"我不舒服"（`Exception`）没法处理；说"骨折，挂了骨科 3 号诊室"（`PdfConversionError` 带 `node_name`）才能对症下药。

**替代方案**

| 方案 | 优点 | 缺点 | 什么时候用它 |
|---|---|---|---|
| **分类自定义异常（本项目）** | 能精准捕获；携带上下文；改文案不影响控制流 | 文件变长（本项目 108 行） | 有多个步骤、且需要差异化处理 ✅ |
| 只用内置异常 + 消息 | 文件短 | 见上：无法分类，或靠字符串匹配 | 单文件小脚本 |
| 用错误码（error code）返回而不是异常 | 控制流显式 | 每层都要手动检查返回值，很容易漏；和 Python 风格不符 | 需要跨语言/跨进程传递时 |
| `ExceptionGroup`（Python 3.11+） | 能一次性抛出多个错误 | 需要 Python 3.11+，用法较新 | **并行执行多个节点、可能同时失败时** |

**优化空间**：
1. **缺 `MongoError`**：`.env` 里配了 `MONGO_URL`，也会往 MongoDB 写元数据，但没有对应的异常类。建议补：`class MongoError(StorageError)`。
2. **异常没带错误码**：如果将来要给前端返回不同提示，建议加 `code` 字段（如 `code="PDF_PARSE_FAILED"`），前端按码做文案映射，比按中文消息匹配可靠得多。
3. `ImportProcessError.__str__` 里已经拼了 `node_name` 和 `cause`，很好。但 `cause` 只是存下来了，**没有用 `raise ... from e`** —— 那样能保留完整 traceback 链条。

---

## §12 依赖注入

**一句话人话**：需要用的东西，**从外面传进来**，而不是自己在里面造。

**它在做什么**

```python
def __init__(self, config: Optional[ImportConfig] = None):
    self.config = config or get_config()      # ← 传了就用传的，没传就用全局单例
```

**不这么做会怎么样**

```python
def __init__(self):
    self.config = ImportConfig()      # ❌ 自己造，写死了
```

后果是**没法测试**。你想验证"当 `max_content_length=100` 时切出来的块是什么样"，只能去改 `.env` 文件，测完再改回来 —— 又慢又容易忘。

有了注入：

```python
test_config = ImportConfig(max_content_length=100)
node = NodeDocumentSplit(config=test_config)   # 干净、瞬时、不污染环境
node(state)
```

**生活类比**：外卖（注入）vs 自己种地（自己 new）。自己种地的话，想换口味得铲掉整片田；点外卖只要换个订单。而且换一个"假的供应商"（测试用配置）来验货成本极低。

**替代方案**

| 方案 | 优点 | 缺点 | 什么时候用它 |
|---|---|---|---|
| **构造函数默认参数注入（本项目）** | 零依赖、零学习成本 | 只在构造时注入一次，运行中改不了 | 配置固定的场景 ✅ |
| 全局单例直接用（不注入） | 最简单 | 无法测试、无法并存多套配置 | 一次性脚本 |
| 方法参数注入 `node.process(state, cfg)` | 更灵活（每次可不同） | 每层都要传参，啰嗦 | 需要每次处理用不同配置时 |
| 依赖注入框架（`dependency-injector`） | 自动化、支持作用域 | 引入框架、学习成本高 | 大型应用 |
| `pytest` 的 `monkeypatch` 改环境变量 | 不用改任何代码 | 测试代码变绕，且是全局副作用 | 不想为测试改造代码时的兜底 |

**优化空间**：现在 `config or get_config()` 用的是"真假值"判断，严格来说是 `config if config is not None else get_config()` 的近似写法。建议改严谨一点 —— 万一将来 `ImportConfig` 实现了 `__bool__` 或 `__len__` 且返回 `0`/`False`，你明明传了配置也会被悄悄换成单例。这是"将来某天会咬你一口"的典型形态。

---

## §13 浅拷贝与深拷贝

**一句话人话**：浅拷贝只换外壳，深拷贝连内脏一起换。

**问题从哪来**

```python
GRAPH_DEFAULT_STATE = {
    "task_id": "",
    "chunks": [],          # ← 注意这个"可变对象"
}

def get_default_state():
    return copy.deepcopy(GRAPH_DEFAULT_STATE)
```

**不这么做会怎么样**

```python
def get_default_state():
    return GRAPH_DEFAULT_STATE          # ❌ 直接返回
```

```python
s1 = get_default_state()
s1["chunks"].append("第一份文档的切片")
s2 = get_default_state()
print(s2["chunks"])          # ['第一份文档的切片']  ← 第二份导入凭空多了数据！
```

**根因**：Python 变量都是**引用**。返回 `GRAPH_DEFAULT_STATE` 返回的是"同一个字典的地址"，改它等于改了模块里的常量。

那用浅拷贝行不行？

```python
return dict(GRAPH_DEFAULT_STATE)        # 浅拷贝
s1["task_id"] = "abc"                   # ✅ 安全，外层是新的
s1["chunks"].append("x")                # ❌ 仍然污染！内层列表还是共享的
```

**浅拷贝只复制最外面一层**，里面的 `chunks` 列表仍然是**同一个对象**。只有 `copy.deepcopy()` 会递归复制到底，`chunks` 变成独立的新列表。

**⚠️ 这是同一类问题的两个常见变体，一起记住**：

```python
def f(acc=[]):          # ❌ 可变默认参数：这个 [] 只创建一次，所有调用共享
    acc.append(1)
    return acc

def f(acc=None):        # ✅ 标准修法
    if acc is None:
        acc = []
```

```python
@dataclass
class C:
    items: list = []    # ❌ 同理，而且是类属性，所有实例共享
    items: list = field(default_factory=list)   # ✅ 见 §7
```

**生活类比**：浅拷贝 = 复印了文件夹封面，里面还是原文件；深拷贝 = 连里面每张纸都复印一份。

**替代方案**

| 方案 | 优点 | 缺点 | 什么时候用它 |
|---|---|---|---|
| **`copy.deepcopy`（本项目）** | 绝对安全，嵌套多深都不怕 | 比浅拷贝慢（本项目状态字典只有 10 多个字段，可忽略） | 状态/数据里含可变对象 ✅ |
| `dict(...)` / `.copy()` | 快 | 嵌套的可变对象仍共享 → 见上 ❌ | 确认没有嵌套可变对象时 |
| 每次**重新构造**一个字面量 | 最安全，也最快 | 字段多了要写两遍（和 `TypedDict` 声明重复） | 字段很少时 |
| 用不可变类型（`tuple` 代替 `list`、`frozenset` 代替 `set`） | 根本不可能被污染 | 没法 append，需要频繁创建新对象 | 数据本来就只读时 |

**优化空间**：`get_default_state()` 现在是对**整个 state** 做深拷贝。等将来 `chunks` 里装了几千条切片（每条还带 1024 维向量）时，每次 `deepcopy` 的开销就不容忽视了。那时的做法是**拆开**：默认状态里只放"小字段"（字符串、布尔），`chunks` 不进默认状态，改为每个节点自己按需创建 —— 即"默认状态只包含不可变值"。这也是 `state.py` 里 `chunks: []` 那个初始值值得警惕的原因。

---

## §14 LangGraph 的状态增量合并（partial update）

**一句话人话**：节点**只需要返回自己改动的那几个字段**，LangGraph 会替你合并进总 state，没提到的字段**保持原值不动**。

**它在做什么**

```python
# node_enrty.py
def process(self, state):
    return {
        "is_md_read_enabled": True,
        "is_pdf_read_enabled": False,
    }                     # ← 只返回 2 个键，state 里其余 10 个字段不用管
```

对照回复里那张"状态增量合并"的图看：左边是合并前的 state，中间是节点返回的 2 个键，右边是合并后 —— 只有 `is_md_read_enabled` 从 `False` 变成了 `True`，其他字段原封不动。

**不这么做会怎么样**

```python
def process(self, state):
    return state          # ← 6 个存根节点现在的写法
```

语法上没错，能跑。但有两个问题：

**① 浪费**：整个字典原封不动传回去，等于做了一遍无意义的"读—写"。10 个字段 × 8 个节点，白做 80 次。

**② 隐患（更严重）**：如果这个节点在处理过程中改了 state 里某个**嵌套可变对象**：

```python
def process(self, state):
    state["chunks"].append(new_chunk)     # 就地修改了！
    return state
```

因为传进来的是**同一个对象**，总 state 在 `return` 之前**就已经被改了**。万一后面某行抛异常，你会得到一个"改了一半"的脏状态 —— 而且完全看不出是谁改的。这叫**隐式就地修改**，是最难查的一类 bug。

正确写法是返回新值，不去改传进来的东西：

```python
def process(self, state):
    return {"chunks": state["chunks"] + [new_chunk]}   # ✅ 生成新列表
```

**生活类比**：报表交接。规范做法是"我只在这个格子上贴一张便签"（返回局部字典）；错误做法是"我把整本报表复印一份，顺手在上面涂改"（返回整个 state），——看起来一样，但你涂改的那一笔已经留在原件上了。

**替代方案**

| 方案 | 优点 | 缺点 | 什么时候用它 |
|---|---|---|---|
| **返回局部字典（LangGraph 官方推荐）** | 意图清晰；不会隐式改状态；支持并行节点安全合并 | 需要知道"我该返回哪些键" | **所有 LangGraph 节点** ✅ |
| 返回整个 state | 不用想"该返回什么" | 见上两个问题 | 早期原型、单节点调试 |
| 用 `Annotated[list, operator.add]` 声明"累加型字段" | 并行节点往同一字段写不会互相覆盖 | 要多写一句类型声明 | 多个节点并行往 `chunks` 里塞数据时 |
| 全部字段都重算一遍再返回 | 状态绝对自洽 | 性能差；复杂逻辑下容易漏字段 | 字段极少、逻辑极简单 |

**优化空间**：本项目现在**风格不统一** —— `node_enrty.py` 返回局部字典（正确），6 个存根节点都 `return state`（待改）。建议统一成局部字典，并在每个节点的 docstring 里写明"**我产出哪些字段**"，这样将来写 `graph.py` 组装时，一眼就能看出节点之间的依赖顺序。同时 `chunks` 这种列表字段，建议用 `Annotated[List[dict], operator.add]` 声明成累加型。

---

## §15 logging 的 Logger / Handler / Formatter 三层

**一句话人话**：日志有三层分工 —— **Logger 负责产生，Handler 负责送出去，Formatter 负责长什么样。**

> ⚠️ 很多教材只讲这三层，容易让人误以为链条是"记录器→处理器→格式器"一条直线。
> **还有第四件 `Filter`（过滤器），但它不在这条线的末端**——它是插在两道关卡上的筛子。
> 完整顺序和实测证据见下面的 **§15.1**。

**日志器（logger）到底是什么东西**

一句话：**日志器是一个"带名字的打日志工具"，它不是日志本身。**

实测 `logging.getLogger("import.demo")` 拿回来的对象身上装着这些零件：

| 属性 | 实测值 | 作用 |
|---|---|---|
| `.name` | `'import.demo'` | 身份牌，日志里印的就是它 |
| `.level` | `0`（NOTSET） | 自己的门槛。0 = 自己不拦，向上问 |
| `.handlers` | `[]` | **喇叭，默认是空的** |
| `.parent` | `'root'` | 上级，没人接就往上送 |
| `.info()` `.warning()` `.error()` | 可调用 | 喊话的方法 |

```python
type(lg)   # <class 'logging.Logger'>
repr(lg)   # <Logger import.demo (WARNING)>
```

⚠️ 括号里那个 `WARNING` 是**有效级别**（沿树往上找到的门槛），**不是** `lg.level`（那还是 0）。别被 repr 骗了。

**两个关键性质**

1. **它是"工具"，不是"内容"** —— 打印 `lg` 本身不会产生任何一条日志。
2. **它是按名字存在全局仓库里的**（实测）：
   ```python
   logging.getLogger("import.demo")  is lg   # True   ← 同名拿回同一个对象
   logging.getLogger("import.other") is lg   # False  ← 换个名字各有一个
   ```

**生活类比**：日志器像**一台带工牌的扩音器**。工牌上写着是谁（`.name`）、音量下限设在多少（`.level`）、上面还有一整套喊话按钮（`.info()` 等）。但它**出厂时没接音箱**（`.handlers` 是空的）—— 所以光有它，喊了也没人听见，得靠 `setup_logging()` 给它（准确说是给 `root`）接上音箱。

---

### §15.0 一条日志的完整旅程（六步，本机实测）

先看全景，再看细节。你写下 `self.logger.info("开始啦")` 之后，这条日志要过 6 道手才出现在屏幕上：

| # | 步骤 | 实测到的真实状态 |
|---|---|---|
| 1 | **发货** | `self.logger.info(...)` 先生成一条 `LogRecord`（装着 logger 名 / 级别 / 消息 / 时间） |
| 2 | **过第一道门槛** | logger 自己的级别是 `NOTSET`(0)，它不拦，而是沿树往上问「最近的门槛是多少」＝ `INFO` |
| 3 | **往楼上送** | logger 自己 `handlers=[]`（空的！），于是沿 `parent` 一路冒泡到 `root` |
| 4 | **过第二道门槛** | `root` 的 Handler 接住。`handler.level` 默认是 `NOTSET`，即它自己不设门槛 |
| 5 | **贴标签** | Formatter 拼成 `时间 - 名字 - 级别 - 消息`，再套上颜色码 |
| 6 | **送出门** | 写进 **stderr**（不是 stdout） |

实测脚本（可自己跑）：`temp/log_flow_test.py`

```bash
cd E:/project/knowledge_base
PYTHONPATH=. ./.venv/Scripts/python.exe -u temp/log_flow_test.py
```

**两个反直觉的实测结果**

**① `logger.handlers` 是空的 —— 节点自己根本不会输出日志**

```
logger.name              = import.node_test
logger.level             = NOTSET   ← 自己不拦
logger.handlers          = []       ← 空的
logger.getEffectiveLevel = INFO     ← 沿树往上找到的第一个门槛
```

节点里的 `self.logger` 只是个**投递口**，它手上没有任何 Handler。日志全靠步骤 3 往上冒泡，冒到 `root` 才被人接住。**这就是为什么必须调 `setup_logging()`：它是在 `root` 上装收发室。**

**② 没有 Handler 时，logging 有个兜底的 `lastResort`**

把 `root` 的 handler 全清掉再打日志，本来以为会彻底消失，结果：

```
root.handlers = 0
logging.lastResort = <_StderrHandler <stderr> (WARNING)>
lg.info("...")     → 无输出（INFO 低于兜底门槛）
lg.warning("...")  → 我是 warning —— 我是裸的，没有时间戳、没有名字
```

`logging.lastResort` 是标准库内置的一个临时工：**当整棵树一个 Handler 都没有时，它顶上，只放行 `WARNING` 以上，而且不套任何格式。**

→ **可操作的诊断信号**：**看到没有时间戳、没有 logger 名的裸日志，就说明 `setup_logging()` 没生效**（或者被清掉了）。这是排查"日志格式不对劲"最快的一条线索。

**调换顺序会怎样**：先打日志、后 `setup_logging()` → 前面那几条已经"走完了没人接"被丢弃，永远看不到。**口诀：先配日志，再打日志。**

---

**它在做什么**

```python
# base.py
logger = logging.getLogger()          # 取 root logger（整棵树的根）
logger.setLevel(logging.INFO)         # 门槛：INFO 以下不放行
handler = colorlog.StreamHandler()    # 输出到控制台
handler.setFormatter(...)             # 装上"模板"
logger.handlers.clear()               # 先清空，防止重复挂
logger.addHandler(handler)            # 挂上去
```

**`import.{节点名}` 的分层魔法**

```python
self.logger = logging.getLogger(f"import.{self.name}")
```

先说清楚这行的身份：**它本身一条日志都不打**。它只是去 logging 的全局仓库按名字取一个日志器，存到 `self.logger` 上。仓库本质是个字典 —— 同名取两次返回**同一个对象**，不同名各有一个（实测 `a is b → True`）。真正的日志是后面 `self.logger.info("...")` 才产生的。

**点号是"树上的路径"，但这棵树是现场挂出来的，不是预置的**

logging 在创建每个 logger 时，会沿名字里的点号逐段往前找祖先，**只认已经创建过的**，一个都找不到就直接挂到 `root`。

实测（本机 `.venv` 验证）：

```python
child = logging.getLogger("import.node_test")
child.parent.name            # → 'root'    ← 注意！不是 import

logging.getLogger("import")  # 显式创建中间层
child.parent.name            # → 'import'  ← 已存在的子 logger 被自动修正了
```

所以本项目**真实的**挂载关系是这样的（中间层 `import` 从没被创建过）：

```
root                              ← setup_logging() 在这挂 Handler
├── import.node_entry             ← 这些子 logger 直接挂在 root 上
├── import.node_pdf_to_md
├── import.node_md_img
└── ...（共 8 个）
```

**结论（重要）**：分层**不影响**日志能不能输出 —— `root` 是共同的祖先，日志照样冒上去，实测在 `import` 上挂 Handler、子级 `import.node_test` 的日志确实被它输出了。

点号真正的价值是**预留了一个统一的管理入口**：

```python
logging.getLogger("import").setLevel(logging.WARNING)             # 一句话管住全部节点
logging.getLogger("import.node_md_img").setLevel(logging.ERROR)   # 也可以只静音某一个
```

第二行这种"按名字单独开关某个节点"的能力，是 `print` 完全做不到的 —— 这是用 logger 而不是 print 的最大理由。

我们实测的输出正是这个效果：

```
2026-09-27 11:44:12 - import.node_test - INFO - --- node_test 开始啦 ---
                       ↑ 这个就是 __init__ 里造的 logger 名
```

**`logger.handlers.clear()` 为什么必须有**

```python
logger.handlers.clear()      # ← 这一行不能删
logger.addHandler(handler)
```

如果反复调用 `setup_logging()` 而不清空，就会有 N 个 Handler 挂在同一个 logger 上，一条日志被打印 N 遍。这是初学者最常见的"日志重复输出"问题，根因就在这一行。加上它以后，`setup_logging()` 变成**幂等**的——调多少次效果都一样。

**不这么做会怎么样**

1. **不分层**：每个节点写 `logging.getLogger()`（不带参数），全落到根 logger 上，日志里看不出是哪个节点打的。
2. **不设级别**：日志库默认只放行 `WARNING` 以上，你的 `logger.info("开始啦")` 一条都不会出现——这就是必须调 `setup_logging(logging.INFO)` 的原因。
3. **不设 Formatter**：默认格式只有消息体本身，没有时间戳，无法排查"是几点出错的"。
4. **顺序搞反**（先打日志、后 `setup_logging`）：日志已经"走完了没人接"被丢弃，前面那几条永远看不到。**口诀：先配日志，再打日志。**

**生活类比**：Logger 是写稿的记者，Handler 是决定投给哪家报社（纸媒？网站？），Formatter 是排版格式。记者写得再好，没有报社接收就是废纸。

**替代方案**

| 方案 | 优点 | 缺点 | 什么时候用它 |
|---|---|---|---|
| **`logging` + `colorlog`（本项目）** | 标准库、无额外依赖（除 colorlog）、功能足够 | 配置代码略长（40 行） | 需要分级日志 + 彩色输出 ✅ |
| `logging.dictConfig()` | 用字典配置，代码短 | 字典格式不直观，且不容易插入自定义逻辑 | 配置项多、需要从文件读配置时 |
| `loguru` | 一行搞定彩色日志、自带轮转 | 第三方库；与标准库混用时行为不完全一致 | **追求极致简洁时强烈推荐** |
| `print` | 零门槛 | 无法分级过滤、无法关闭、没有时间戳 | 临时调试 |
| `rich.logging.RichHandler` | 彩色 + 漂亮的 traceback | 依赖较大 | 已经在用 `rich` 做终端输出时 |

**优化空间**：
1. **输出到文件**：现在只输出到控制台。生产环境需要同时写文件（可以考虑 `RotatingFileHandler` 做按大小轮转）。
2. **补 `FileHandler` 时注意格式**：文件里**不该带 ANSI 颜色码**（会是乱码），所以文件 Handler 要用标准 `logging.Formatter` 而不是 `colorlog.ColoredFormatter`。
3. **`colorlog.StreamHandler()` 默认走 stderr，不是 stdout** —— 实测：日志和 `print` 混用时，两个流分开缓冲，看到的先后顺序会错乱（日志看起来"跑到前面去了"）。将来写 `graph.py` 时如果在节点里混用 print 和 logger，排查顺序会被误导。想统一走 stdout 就写 `colorlog.StreamHandler(stream=sys.stdout)`；更彻底的做法是**别用 print，全走 logger**。
4. ⚠️ **别把密钥打进日志**：`config.py` 里有 `openai_api_key`、`minio_secret_key`。将来如果打印整个配置对象，密钥会直接落到日志文件里。建议给 `ImportConfig` 加一个脱敏的 `__repr__`，或者在这些字段上做掩码（只显示 `sk-****`）。
5. **`setup_logging()` 目前要手动调用**：`base.py` 定义了它但没自动执行。建议在程序入口（`src/knowledge_base/__init__.py` 的 `main()`）统一调一次，避免某个节点单独运行时忘了调。
6. **`setup_logging` 内的 `logger.handlers.clear()` 是全局副作用**：它清的是 **root** 的 handler，会顺手干掉别的库（如 langchain、httpx）可能挂在 root 上的 handler。更稳妥的写法是只清自己加的那个，或者给 `import` 这一层单独建一棵子树。

---

### §15.1 `Filter` 在哪一步？——别把它串成第四环

**一句话人话**：Filter **不是链条末端的第四个零件**，它是**贴在两道关卡上的筛子**。日志要过两道关，每道关都是"先测级别、再查 Filter"。

**先纠正一个很常见的错误记法**

如果你把它记成下面这样一条直线，是错的：

```
记录器 → 处理器 → 格式器 → 过滤器        ✗ 错的
```

`Formatter` 确实偏后，但 `Filter` **不在这里**——它在前面**各层各插一道**。真实链路是这样（本机实测逐步验证过）：

```
logger.warning("消息")                 ← 日志器：日志在这一刻诞生
   │
   ① 级别闸：logger 自己的级别          ← 不过就直接结束，后面全不发生
   ② 筛子　：logger 自己的 filter       ← 返回 False 也直接结束
   │
   ③ 往上冒：沿 parent 链，把这条日志交给路上每个 logger 挂的 handler
   │    对每一个 handler：
   │      ④ 级别闸：handler 自己的级别  ← 不过就跳过这个 handler
   │      ⑤ 筛子　：handler 的 filter   ← 返回 False 也跳过
   │      ⑥ Formatter 排版             ← 注意：排版是 handler 调用的
   │      ⑦ 写出去（控制台 / 文件 / 网络）
   │
   ⑧ 一路上一个 handler 都没接住 → logging.lastResort 兜底裸吐（无时间戳）
```

**用一句话记住顺序**：**测身高 → 查证件 → 排版 → 出门**。级别闸是测身高（不够高直接劝返，**根本不查证件**），filter 是查证件。

**Filter 长什么样（和你写的类一样）**

Filter 就是一个普通的类，必须有一个叫 `filter` 的方法，返回 `True`（放行）或 `False`（拦掉）：

```python
class OnlyMdNode(logging.Filter):
    def filter(self, record):
        return "node_md" in record.name        # 只放行名字里带 node_md 的

logging.getLogger().addHandler(h)
h.addFilter(OnlyMdNode())                      # 挂在 handler 上
```

**另一种用法：直接用名字筛 —— `logging.Filter("xx")`**

标准库的 `Filter` 构造函数**自带一个 `name` 参数**，不传就是"一律放行"，传了就变成"按名字的前缀筛"。匹配规则只有两条：

1. 名字**完全相同** → 放行
2. 名字**是它的子层**（后面紧跟一个点号）→ 放行

实测（`temp/filter_name_test.py` 可复跑）：

| 被筛的名字 | `Filter("import")` | `Filter("import.node")` |
|---|---|---|
| `import` | 放行 | 拦掉 |
| `import.node` | 放行 | 放行 |
| `import.node.md_img` | 放行 | **放行**（真子层） |
| `import.node_entry` | 放行 | **拦掉** ← 坑在这 |
| `import.nodex` | 放行 | 拦掉 |
| `other` | 拦掉 | 拦掉 |

⚠️ **最容易踩的一条**：`Filter("import.node")` **拦掉了 `import.node_entry`**。因为这个项目的节点名用的是**下划线**（`import.node_entry`、`import.node_md_img`），不是点号分层——`node_entry` 是一个完整名字，不是 `node` 下面的一层。**前缀匹配的是"点号分隔的整段"，不是"任意字符串的开头"。**

所以本项目要用名字筛，该写 `Filter("import")`（放行全部 7 个节点），或者用 `Filter("import.node_entry")` 只放行某一个。

**别把它和"名字按点号组树"混为一谈——这是两件事**

| | 靠什么 | 决定什么 |
|---|---|---|
| **点号组树** | `logging.getLogger()` 建 logger 时的名字 | 日志往上冒时**经过哪些祖先的处理器**（冒给谁） |
| **点号前缀筛选** | `logging.Filter("xx")` | 这条日志**要不要**（放不放行） |

一句记法：**组树管"冒给谁"，Filter 管"要不要"。**

**四条实测结论（都不是推断）**

| 你可能的想法 | 实测结果 |
|---|---|
| 级别和 Filter 谁先判断？ | **级别先**。级别没过时，filter **一次都不会被调用**——实验里 `root.info()` 打出去，logger 上的 filter 完全没响 |
| 祖先 logger 的 filter 会被调用吗？ | **不会**。用 `import.child` 打日志时，`root` 上的 filter 一次都没响，只有 `child` 自己的和 handler 的响了 |
| Filter 和 Filter 的先后？ | **logger 上的先，handler 上的后**（实测输出顺序：`logger 上的` → `handler 上的` → 排版输出） |
| Formatter 是谁调用的？ | **handler**。`Handler.emit()` 内部调 `self.format(record)`——所以换 handler 的 formatter 就能给"同一个 logger、不同去处"配不同格式 |

→ **最实用的一条**：想做**全局过滤**（比如"所有节点日志里都不要出现密钥"），要挂在 **handler** 上，**不能挂在祖先 logger 上**——挂了不生效，还看不出来。

**它在做什么（对照本项目）**

本项目 `setup_logging()` 里**没有用 Filter**，因为需求简单（全都要打，只是级别不同）。`logger.handlers.clear()` 那句其实起到了类似 filter 的作用——不过是"全部清掉"，粒度粗得多。

**不做会怎么样**

不用 Filter 也不会报错，只是**少一种精准控制**。举例：你想"只把 `import.node_bge_embedding` 的日志写进文件、其它节点不写"，用 Filter 是三行代码的事；不用 Filter 就只能靠**给每个节点单独配 handler**，或者干脆放弃这个需求。

**生活类比**：级别是**身高线**，Filter 是**安检门**。先量身高，够高了才让你过安检门；安检门自己还可以按规则再拦一次（"今天液体一律不许带"）。**身高不够的人，安检门根本见不到他。**

**替代方案**

| 方案 | 优点 | 缺点 | 什么时候用它 |
|---|---|---|---|
| **`Filter`（本节）** | 标准库自带；可以按任何字段判断（名字、消息内容、自定义字段） | 要写一个类（3~5 行） | 需要"按内容/名字精准筛选"时 ✅ |
| `logging.Filter("名字")` | **一行搞定**，不用自己写类 | 只能按名字前缀筛，粒度固定，且点号必须是真分隔符 | 只想"放行某一层日志"时 ✅ |
| 只调级别 `setLevel` | 一行搞定 | 只能按级别筛，无法按名字或内容筛 | 需求就是"少打点 debug" |
| `logging.dictConfig()` 的 `filters` 段 | 配置和代码分离 | 配置字典本身也要写 filter 类的路径，没省事 | 配置从文件读的系统 |
| 在 `self.logger.info()` 前加 `if` | 零学习成本 | 判断散落在业务代码里，改需求要翻遍全项目 | 临时、一次性的判断 |

**优化空间**

1. **本项目真正值得加的一个 Filter**：**密钥过滤器**——`config.py` 里躺着 `openai_api_key`、`minio_secret_key`，一旦哪次日志打印了整个配置对象，密钥就进文件了。一个挂在 handler 上的 filter，检查 `record.getMessage()` 里有没有 `sk-` 就能兜住。
2. **Filter 还能当"限流器"用**：同一个错误在循环里刷屏时，filter 可以记住"这条已经打过 10 次了，不再打"（官方文档里就有这个例子）。
3. ⚠️ **别把 filter 挂在祖先 logger 上**——见上面那张表第二行，**不生效且无声**，是最容易白忙一场的写法。

---

### §15.2 logger 名字是怎么拼出来的？—— `self.name` 从哪来

**一句话人话**：节点名字**不是"传"进去的**，是**子类里写的一行类属性，被读出来、拼上前缀**得到的结果。整个过程只有"读"和"拼"，没有"传参"。

**第一步：`name` 是"类属性"，不是"实例属性"**

`base.py` 里写的是这一行（注意**没有** `self.`）：

```python
class BaseNode(ABC):
    name: str = "base_node"      # ← 直接写在类体里，这叫「类属性」
```

而**不是**这样：

```python
    def __init__(self):
        self.name = "base_node"  # ← 写在这里就叫「实例属性」，每造一个对象存一份
```

区别用实测最清楚——造一个 `TestNode()`，看它身上到底装了什么：

```python
n = TestNode()
n.__dict__                    # {'config': ..., 'logger': ...}  ← 没有 name！
TestNode.__dict__["name"]     # 'node_test'                    ← 名字在类身上，不在对象身上
```

`__dict__` 就是"这个对象自己身上带的小本子"。**实例的小本子上只有 `config` 和 `logger`，没有 `name`** ——因为 `name` 是写在类上的，属于"这个模具共享的一份"。

**第二步：`n.name` 是怎么找到的（查找顺序）**

你写 `n.name` 时，Python 按这个顺序找，**找到第一个就停**：

| 顺序 | 去哪找 | 实测结果 |
|---|---|---|
| 1 | 对象自己的小本子（`n.__dict__`） | 没有 |
| 2 | 它的类（`TestNode`） | **找到了：`'node_test'`** ✅ |
| 3 | 父类（`BaseNode`） | 有 `'base_node'`，但轮不到它 |
| 4 | 更上层（`ABC` → `object`） | 没有 |

实测 `TestNode.__mro__`（查找链）就长这样：

```
1. TestNode      ← 在这找到 name = 'node_test'
2. BaseNode      ← 也有一份 name = 'base_node'
3. ABC
4. object
```

→ **子类里写的那一行赢**，因为它排在前面。这就是 `base.py` 注释里说的"子类必须覆盖这个属性"——**覆盖 = 同名盖掉，排在前面就先被找到**。

**第三步：三行，把它变成 logger 名**

`base.py` 第 126 行那件事拆开看：

```python
self.name                      # ① 读属性：沿查找链找到 'node_test'
f"import.{self.name}"          # ② 拼接：变成 'import.node_test'
logging.getLogger(上面那个串)   # ③ 去仓库按这个名字拿（没有就现造）一个日志器
```

实测两个节点对照：

| 类 | `self.name` | 拼出来 | `logger.name` |
|---|---|---|---|
| `TestNode` | `node_test` | `import.node_test` | `import.node_test` ✅ |
| `NodeMDImg` | `node_md_img` | `import.node_md_img` | `import.node_md_img` ✅ |

**第四步：为什么前缀要叫 `import`**

**纯粹是自己定的约定，Python 完全不要求。** 改成 `kb.`、`myapp.` 一样能跑。

它真正的价值是"**一句话管住全部节点**"：

```python
logging.getLogger("import").setLevel(logging.ERROR)     # 7 个节点全部静音
```

而这一行**真的能生效**，靠的是之前讲过的一个机制——实测：

```
执行 getLogger("import").setLevel(ERROR) 之前：
    import.node_test 的 parent = 'root'

执行之后：
    import.node_test 的 parent = 'import'     ← 被自动修正了
```

因为这一行才**第一次真正创建出 `import` 这一层**，此前它并不存在；子 logger 的 `parent` 在那一刻从 `root` 改挂到了它下面。之后子节点判断级别时沿 `parent` 往上找门槛，第一个就撞上 `import` 的 `ERROR`。

→ **如果当初名字五花八门**（`a_node` / `b_node` / `c_node`），就只能一个一个 `setLevel`，或者全项目搜一遍改。

**生活类比**：`name = "node_test"` 是**工位上挂的工牌**（挂在墙上，不是攥在手里）。开工时（`__init__`）系统照工牌念一遍，抄进对讲机频道名：`import.` + 工牌名。所以——

- 想改频道名 → 改工牌（改类属性那一行）就够了
- 工牌挂在**墙上**（类），不是攥在**手里**（实例），所以同一型号的工位共享同一块工牌

**不做会怎么样**

| 写法 | 后果 |
|---|---|
| 子类**没写** `name` | 不报错。它会**继承父类的 `"base_node"`** → 8 个节点的 logger 全叫 `import.base_node`，日志里**分不清是哪个节点打的** |
| 名字**写重了**（两个节点都叫 `node_test`） | 也不报错。两个节点共用同一个 logger，日志里也分不清 |
| 干脆不设 `name`，`getLogger("import.")` | 名字变成 `import.`，日志里只显示 `import.`，等于没名字 |

⚠️ **注意第一种**：这类错误**不会抛异常**，只会让日志变得没用。跟前面讲抽象类的道理一样——**能自动拦住你的地方不多，这类"约定"要靠自己守。**

**替代方案**

| 方案 | 优点 | 缺点 | 什么时候用它 |
|---|---|---|---|
| **类属性 `name = "xxx"`（本项目）** | 一行、直观、可被子类覆盖 | 忘了写不报错（静默降级成父类的名字） | 常规做法 ✅ |
| `type(self).__name__` | 完全不用写，自动用类名 | 名字跟类名死死绑定，改类名就改日志名；且拿不到中文/自定义名 | 不在乎日志名长相的小项目 |
| `__name__`（模块名） | 自动、和文件对应 | 是"文件级"粒度，一个文件里多个类会重名 | 一个文件一个类时 |
| 在 `getLogger(...)` 里**硬编码** | 最直白 | 每个节点都要改父类代码，等于放弃继承 | 只有一两个节点时 |
| `@dataclass` + 类变量 | 声明式 | 多一层概念，收益不明显 | 已经在用 dataclass 的组织配置时 |

**优化空间**

1. **加一道自检**：现在 `name` 忘了写只会静默降级。可以在 `BaseNode.__init_subclass__`（子类被创建时自动执行的钩子）里加一行：发现子类的 `name` 还是 `"base_node"` 就直接抛错。这样"忘写工牌"这件事就**从静默变成立刻报错**，和 `@abstractmethod` 的效果一样。
2. **加名字校验**：要求所有节点名都以 `node_` 开头，保证 `logging.getLogger("import")` 这句话永远管得住全部节点。
3. **前缀应该来自配置**：现在 `"import"` 是硬编码在 `f"import.{self.name}"` 里的。如果以后有第二条流水线（比如"导出"），就会出现 `import.` 和 `export.` 两套前缀，建议把它提到 `ImportConfig` 里，或改成从 `__name__` 里推导。

---

## §16 泛型占位符 `T`（TypeVar）

**一句话人话**：`T` 是一个**代号**，它不代表某个具体类型，而是代表"**待定**"。写 `def f(x: T) -> T` 的意思是"传进来什么类型，就吐出去什么类型"——重点在**两端一致**，而不在"必须是某种类型"。

**它在做什么**

`base.py` 顶部有这么一行：

```python
from typing import TypeVar
T = TypeVar("T")      # 造一个类型代号，名字叫 T
```

然后 `__call__` 和 `process` 都标成 `T`：

```python
def __call__(self, state: T) -> T:      # 收进来 T，吐出去 T
def process(self, state: T) -> T:       # 同一个 T
```

**不做会怎么样**

实测：`T` 在**运行时不做任何检查**。把 `int`、`str`、`list` 三种类型都塞进一个标了 `T` 的函数，一个都没被拦：

```
identity(123)          → 收到 123        类型 int
identity("我是字符串")   → 收到 '我是字符串'  类型 str
identity([1, 2, 3])    → 收到 [1, 2, 3]    类型 list
```

所以"不写 `T`"的**直接后果**是：运行时毫无差别，程序照跑。差别只出现在两处：

| 场景 | 不写类型标注 | 写了 `T` |
|---|---|---|
| 运行时 | 一样跑 | 一样跑（**不检查**） |
| IDE 补全 | `state.` 后面不出提示 | 能提示出状态字典的字段 |
| mypy 静态检查 | 不做检查 | 发现"传入和返回类型对不上"时报错 |

**生活类比**：`T` 像快递单上"**收件人**"那一栏留空。空着不影响包裹先寄出去，但填上之后，快递员（类型检查器）才能核对"寄给张三的包裹是不是交给了张三"。`T` 表达的就是这种**两端的对应关系**。

**替代方案**

| 方案 | 优点 | 缺点 | 什么时候用它 |
|---|---|---|---|
| **`TypeVar` 泛型（本项目）** | 表达"传入与返回一致"的约束；不绑死具体类型 | 多一行定义，初学要多理解一个概念 | 基类/工具类要支持任意状态类型时 ✅ |
| 直接写 `ImportGraphState` | 最直观，IDE 补全最准 | 基类被绑死在这个项目的数据结构上，想复用就得改 | 不打算复用的项目内代码 |
| 不写标注（`def process(self, state)`） | 零负担 | 失去全部 IDE 补全和静态检查 | 快速原型 |
| `Any` | 表达了"什么都行" | 等于放弃检查，比不写还糟（给了虚假的安全感） | 几乎不该用 |

**本项目为什么选 `T`**：`BaseNode` 是**框架层**，它不该知道"状态长什么样"（那是业务层 `state.py` 的事）。用 `T` 就把这层解耦了——将来换个项目、换一种状态结构，`base.py` 一个字都不用改。

**优化空间**：

1. `T` 目前**不受约束**，任何类型都能填。可以加约束，比如 `T = TypeVar("T", bound=dict)`，表达"至少得是个字典"，让检查器更严格。
2. `ImportGraphState` 是 TypedDict，而 TypedDict 的泛型标注支持有限——实际收益主要来自 IDE 补全，别指望 mypy 能查出多深的问题。
3. 这类"只在开发期生效"的标注，**值得配一个 pre-commit 钩子跑 mypy**，否则写了也没人看。

---

## 附录：读代码的正确顺序

概念搞懂了，再回头看代码就顺了。建议这个顺序：

```
1. base.py        ← 先看类图（回复里第 1 张图），再看 __init__、__call__
2. state.py       ← 看"托盘"长什么样，配合增量合并图（第 2 张图）
3. config.py      ← 看配置怎么进来。注意那个 MODEL 键名 bug
4. exceptions.py  ← 看错误怎么分类
5. node_enrty.py  ← 第一个真正有逻辑的节点
6. node_test.py   ← 日志机制的完整验证
7. 其余 6 个节点   ← 每个文件头部都写了"它在流水线的第几步、要干什么"
```

**遇到看不懂的名词时的判断流程**：

1. 这个名词是 Python 语言层面的吗？（类、继承、装饰器、拷贝…）
   → 查本手册 §1~§9
2. 是框架层面的吗？（LangGraph 的节点、状态、条件边…）
   → 查 §14，或直接在代码里搜 `LangGraph` 相关注释
3. 是"为什么这么设计"吗？（为什么收敛配置、为什么自定义异常…）
   → 查 §9~§12
4. 是"这一行为什么这么写"吗？
   → 看代码里的行内注释，那里只讲这个

**如果本手册里有你没看懂的表述，直接指出来** —— 说明我写得还不够人话，我来重写那一段。
