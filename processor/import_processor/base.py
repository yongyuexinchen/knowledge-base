# processor/import_processor/base.py

r"""
所有节点共用的"外壳"
================================================================================
这个文件只干一件事：把 8 个节点都需要的重复动作写在一个父类里。

每个节点执行时都要做同样的一套动作：
    打一行"开始啦" → 干活 → 打一行"完成啦" → 出错了就包装成统一的错误再抛
8 个节点抄写 8 遍太蠢，所以写在父类 BaseNode 里一次。
子类只要写"干活"那一小段（process 方法），剩下的父类全包。

数据怎么流（state 是贯穿全流程的大字典，定义在 state.py）：

    LangGraph 把 state 交给 __call__
        → __call__ 打"开始啦"
        → 转交给子类的 process(state)   ← 真正的加工在这里
        → process 返回一个字典（只有它改动的字段）
        → __call__ 打"完成啦"，把这个字典还给 LangGraph 合并进总 state

这个文件里有什么：
    class BaseNode     所有节点的父类（模板）
    setup_logging()    程序启动时调一次，日志才会带时间带颜色打到屏幕上

遇到看不懂的名词 → 查 docs/CONCEPTS.md（下面用 §数字 指到具体章节）
"""


from abc import ABC, abstractmethod   # ABC = 让类变成"不许直接用的模板"；abstractmethod = 给方法盖"子类必须重写"的章（§3、§4）
from typing import TypeVar, Optional  # TypeVar = 类型占位符（§16）；Optional[X] = "X 或者 None"
import logging                        # Python 自带的日志模块
import colorlog                       # 让日志带颜色（自带的 logging 不会上色）

# 项目内部导入。路径从项目根开始写，所以运行时的当前目录必须是项目根。
from processor.import_processor.config import ImportConfig, get_config
from processor.import_processor.exceptions import ImportProcessError

# T 是"类型占位符"：本身没有值，表示"传进来什么类型，就返回什么类型"。
# 在本项目里，T 实际就是 state 那个大字典（ImportGraphState）。
# 为什么不直接写 ImportGraphState？因为父类不该知道子类用的字典长什么样，
# 这样将来换状态类型，这个文件一行都不用改。（详见 §16）
T = TypeVar("T")


"""
1、抽象的类（ABC），子类需要实现这个类
2、抽象的方法（@abstractmethod process），子类需要实现这个方法
3、name属性，子类必须覆盖这个属性
4、__init__() 方法中初始化了日志记录器，日志记录器的名字是 self所在类的名字
5、__init__() 方法中初始化了全局配置，获取全局单例配置对象
6、__call__() 方法的调用时机
    (1)对象 = 类名()
    (2)结果 = 对象()     圆括号调用了__call__()方法
7、self.process()， 当前这句话是从哪调用过来的，process()就定义在哪个位置
8、未来可以在父类的process()中实现任务追踪
9、封装了统一日志处理，使用logging、colorlog
    注意：使用日志记录器记录日志时一定要先激活日志setup_logging(logging.INFO)，并指定日志级别

"""
# ↑ 你自己的笔记，原样保留。补三处小修正：
#   第 4 条：logger 名不是"类名"，是拼出来的 f"import.{self.name}"，只是长得像。
#   第 5 条："全局单例"= 全程序只造一份配置对象，大家共用同一份（§10）。
#   第 7 条：说得对。准确讲：self 是子类造出来的对象，Python 会先在子类里找
#            process，找不到才去父类 —— 所以实际跑的一定是子类写的那个。


class BaseNode(ABC):
    """
    所有节点的父类：只管"外壳"，不管具体加工。

    外壳 = 每个节点都要做的三件事：
        ① 执行前后各打一行日志（"开始啦" / "完成啦"）
        ② 把子类抛出的任何错误，包装成统一的 ImportProcessError 再往上抛
        ③ 把 state 转交给子类的 process()，再把它返回的字典交还出去

    子类要遵守两条规定：
        · 写一个类属性  name = "node_xxx"   （节点名，打日志、报错都靠它）
        · 实现 process(self, state) 方法    （真正加工数据的地方）

    为什么 BaseNode 自己不能被创建（不能写 BaseNode()）？
        类名后面写了 (ABC)，它就成了"模板类"（抽象类，§3）。
        模板里有个盖了 @abstractmethod 章的方法 process —— 意思是
        "这个方法我故意留空，子类必须自己写"。
        只要这个方法没被子类写出来，Python 就不许这个类被创建对象，
        一创建就报 TypeError（§4.3 有完整实测）。
        好处：忘写 process 的节点，在"造对象"那一刻就报错，
        不会混进流水线跑半天才发现没干活。
    """

    # 类属性：写在类里、前面没有 self. 的变量。
    # 子类写一行 name = "node_pdf_to_md" 就把它换掉了。
    # 这个名字被用在三个地方：
    #   ① 日志工具的名字   → "import.node_pdf_to_md"
    #   ② 日志文本         → "--- node_pdf_to_md 开始啦 ---"
    #   ③ 报错时告诉你     → 是哪个节点挂了
    name: str = "base_node"

    def __init__(self, config: Optional[ImportConfig] = None):
        """
        造节点对象时跑一次，只准备两样东西：配置、日志工具。
        这里还接触不到 state（数据还没进来）。

        输入 config：
            哪来的：两种可能 ——
                ① 造节点时传进来：MyNode(config=某个配置对象)
                ② 不传（平常都这样）→ 这行代码会自动去拿"全局共享的那份"
            为什么要留这个参数：为了测试。比如想验证"切片上限改成 100 会怎样"，
                传一个改过的配置对象进来就行，不用去改 .env 文件。

        输出：
            没有返回值。但对象上多了两个属性，之后 process() 里用：
                self.config  ← 读参数用（比如切片上限是多少）
                self.logger  ← 打日志用
        """
        # config 是"假值"（比如 None）时，就去拿全局共享的那份配置。
        # 注意：这是按真假判断，不是严格按"是不是 None"判断 ——
        # 如果哪天传入一个"内容为空的配置对象"，也会被当成没传（小隐患，暂无影响）。
        self.config = config or get_config()

        # 按名字去 logging 的"总仓库"里取一个日志工具，存到 self.logger。
        # 这行本身**一条日志都不打**，只是"取工具"。
        # 名字拼成 "import.节点名"，带点号的好处（§15）：
        #   将来可以按名字统一管理，比如一句话静音某个节点：
        #       logging.getLogger("import.node_md_img").setLevel(logging.ERROR)
        #   这种"按名字单独开关"是 print 做不到的。
        self.logger = logging.getLogger(f"import.{self.name}")

    def __call__(self, state: T) -> T:
        """
        节点被执行时的**唯一入口**。LangGraph 调用节点，调的就是它。

        名字为什么是两个下划线包着的 __call__（§5）：
            这是 Python 的约定 —— 类里定义了 __call__，这个类的对象就能
            "像函数一样被圆括号调用"：
                node = TestNode()    # 括号左边是类名 → 走 __init__
                node(state)          # 括号左边是对象 → 走 __call__（就是这里）
            LangGraph 内部就是用 node(state) 这种方式跑节点的，
            所以没有 __call__ 的话，整个图一步都跑不起来。

        输入 state：
            哪来的：LangGraph 给的（不是上一个节点直接递的）。
                   上一个节点只返回它改动的几个字段，LangGraph 会先合并好，
                   所以你拿到的永远是"到目前为止的完整 state"。
            本方法自己不读里面任何字段，原样转交给 process()。

        加工（三步，都是外壳动作）：
            1. 打日志："--- 节点名 开始啦 ---"
            2. 调 self.process(state) —— 真正的加工在这一步，本方法不管
            3. 打日志："--- 节点名 完成啦 ---"

        输出：
            返回 process() 的返回值 —— 一个字典，只含本节点改动的字段，
            例如 {"is_md_read_enabled": True, "is_pdf_read_enabled": False}
            交给 LangGraph 合并进总 state，再流向下一节点。

        出错时：
            process() 里不管抛什么错，都在这里统一包装成 ImportProcessError，
            附上节点名再抛出去 —— 上层一看就知道是哪个节点挂的。
        """
        try:
            # 1. 父类统一打"开始"日志，子类想漏也漏不掉
            self.logger.info(f"--- {self.name} 开始啦 ---")

            # 2. 调子类写的 process。self 是子类对象，Python 先在子类里找
            #    process，所以实际执行的一定是子类的版本（§2 继承查找顺序）。
            result = self.process(state)

            # 3. 统一打"完成"日志
            self.logger.info(f"--- {self.name} 完成啦 ---")

            return result

        except Exception as e:
            self.logger.error(f"{self.name} 执行失败: {e}")

            # 包装成项目自己的异常类型再抛。message 是错误原文，
            # node_name 告诉上层是哪个节点，cause 保留原始错误对象。
            # 可改进：结尾加 from e，报错链条会更完整（能追溯到根因）。
            raise ImportProcessError(
                message=str(e),
                node_name=self.name,
                cause=e
            )

    @abstractmethod
    def process(self, state: T) -> T:
        """
        真正加工数据的地方。子类**必须**自己写一个（这是每个节点唯一要写的业务代码）。

        输入 state：父类 __call__ 原样转交过来的完整大字典。
            每个节点该读哪几个字段、写哪几个字段，写在各自的节点文件里
            （对照总表见 docs/FLOW.md）。

        输出：返回一个字典，**只装本节点改动的字段**，不要把整个 state 原样返回。
            例：入口节点只返回两个开关字段，其余字段一个字不提。

        为什么函数体只有一个 pass？
            因为这个方法永远不会被真正执行 —— 子类必须写自己的版本盖掉它，
            否则连对象都造不出来。pass 纯粹是为了语法完整（函数体不能是空的）。

        @abstractmethod 的作用（§4）：
            给方法盖一个"子类必须重写"的章。子类没写，Python 就不让造对象。
            谁负责拦？分两步（§4.3 有实测）：造类时先记账，造对象时查账，
            账上有未实现的方法就抛 TypeError。
        """
        pass

    def log_step(self, step_name: str, message: str = ""):
        """
        打一条"步骤标记"日志，用来标记节点内部的小步骤。

        输入：
            step_name : 步骤名，写代码的人自己起的，比如 "MCP查询"
            message   : 可选，补充说明；不传就只打 "[步骤名]"

        输出：
            没有返回值。产生一条 INFO 日志，长这样：
                2026-09-27 14:00 - import.node_test - INFO - [MCP查询] 开始执行
            以后在日志里搜 "[MCP查询]" 就能把相关行全筛出来。
        """
        log_msg = f"[{step_name}]"
        if message:
            log_msg += f" {message}"   # 有补充说明才拼上去，避免尾巴多个空格
        self.logger.info(log_msg)


# ================================================================================
# 日志配置：为什么单独放在类外面？
# 因为"配日志"是整个程序启动时做一次的事，跟任何一个节点、跟数据加工都无关。
# ================================================================================


def setup_logging(level: int = logging.INFO):
    """
    配置日志系统：让日志带时间、带名字、带颜色，输出到控制台。
    程序启动时**必须先调一次**，不然日志都看不见。

    输入 level：
        哪来的：调用方传的，不传默认 INFO。
        是一个整数，不是字符串。级别从低到高：
            DEBUG(10) < INFO(20) < WARNING(30) < ERROR(40) < CRITICAL(50)
        只有 >= level 的日志才会显示，低于的直接丢弃。
        例：setup_logging(logging.INFO) 之后，debug 级的日志就不显示了。

    加工（五步）：
        1. 拿到 root 日志工具（所有日志最终都会传到这里，§15）
        2. 给它设级别门槛
        3. 造一个"输出到控制台"的输出器（handler）
        4. 给输出器装上格式模板（时间 + 名字 + 级别 + 内容 + 颜色）
        5. 先清掉旧输出器，再挂上新的

    输出：
        没有返回值。效果是 root 日志工具上多了一个输出器，
        之后任何节点打日志，都会被它打印到 stderr（注意：不是 stdout）。

    副作用（两件要知道的事）：
        ① 改的是全局 root，整个程序都受影响
        ② 会清掉别人挂的输出器 —— 比如 langchain 自己挂的也会被清掉（实测过）

    不调它会怎样（实测）：
        INFO 级日志全部静默消失，你会以为代码没跑到。
        WARNING 以上的能被 logging 内置的兜底机制打出来，但是"裸"的
        （没时间戳、没有名字）。所以有个诊断口诀：
        ★ 看到没有时间戳的日志 = setup_logging 没生效。
    """

    # 取 root 日志工具：getLogger() 不传名字，取到的就是"根"，
    # 所有带名字的日志工具（"import.xxx"）打的日志最终都会传到它这里。
    logger = logging.getLogger()

    # 设级别门槛：低于这个级别的日志直接丢掉
    logger.setLevel(level)

    # 造一个"输出到控制台"的输出器，用 colorlog 版本是为了能上色
    handler = colorlog.StreamHandler()

    # 装格式模板。%(...)s 是 logging 的占位符，各段的含义：
    #   %(log_color)s  颜色控制（colorlog 专有，按级别变色）
    #   %(asctime)s    时间，长什么样由 datefmt 决定
    #   %(name)s       日志工具名，就是 __init__ 里拼的 "import.节点名"
    #   %(levelname)s  级别名（INFO / ERROR ...）
    #   %(message)s    你写的那句话
    handler.setFormatter(colorlog.ColoredFormatter(
        '%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'bold_red',
        }
    ))


    # 先清掉旧输出器再挂新的 —— 这行不能删。
    # 不清的话，这个函数每被调一次就多挂一个输出器，
    # 同一条日志会被重复打印 N 遍（"日志重复输出"最常见的原因）。
    logger.handlers.clear()
    logger.addHandler(handler)
    file_handler = logging.FileHandler("final.log", encoding="utf-8")
    file_handler.setFormatter(colorlog.ColoredFormatter(
        '%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'bold_red',
        }
    ))
    logger.addHandler(file_handler)