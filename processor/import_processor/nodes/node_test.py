# processor/import_processor/nodes/node_test.py

# logging 是 Python 自带的日志模块。这里 import 它不是为了打日志，
# 是为了用 logging.INFO 这个常量（值是 20）—— 见文件末尾。
import logging

# Dict 只用于 process 的类型标注。注意这里用的是普通 dict，
# 不是项目自己的 ImportGraphState —— 试验田这样写没问题，
# 正式节点应该统一用 ImportGraphState（IDE 才能补全字段名）。
from typing import Dict

# 同时导入父类 BaseNode 和日志配置函数 setup_logging。
# 其他节点文件只导 BaseNode —— 因为只有这里需要"手动开日志"。
from processor.import_processor.base import BaseNode, setup_logging


class TestNode(BaseNode):
    """
    日志与基类行为的试验节点（不是业务节点，不进流水线）。

    它是学习用的"试验田"，验证三件事：
      ① 父类的 __call__ 包装生不生效（能不能打出"开始啦/完成啦"）
      ② 日志级别过滤符不符合预期（debug 该不该出现）
      ③ log_step() 打出来的方括号格式长什么样

    正式跑图前建议删掉，或挪到 tests/ 目录。
    """

    name = "node_test"

    def process(self, state: Dict) -> Dict:
        """
        故意打四种级别的日志，观察"哪些会被打印、长什么样"。

        输入 state：
            哪来的：父类 __call__ 传进来的。
            本节点用它吗：**完全不用** —— 纯粹为了满足父类规定的方法格式
            （父类要求 process(self, state)，少一个参数就报 TypeError）。

        加工：
            **不改任何数据**，只做一件事：往日志系统写 4 条不同级别的日志。
            1. debug   → 低于门槛，不会显示（这就是要观察的现象）
            2. error   → 会显示，红色
            3. warning → 会显示，黄色
            4. log_step("MCP查询", "开始执行") → 显示 [MCP查询] 开始执行

        输出：
            返回空字典 {} = "我什么都不改，只打了日志"。
            这是合法的：合并空字典等于没变化。
        """
        # ── 四级日志演示 ─────────────────────────────────────────────────
        # 前提：日志已经被 setup_logging() 打开，且门槛是 INFO。
        # DEBUG(10) < INFO(20)，所以下面这行**不会有任何显示** ——
        # 这不是 bug，是级别过滤在正常工作。想看到它，把门槛降到 DEBUG。
        self.logger.debug(f"{self.name}正在debug")

        # ERROR(40) ≥ INFO(20) → 会显示，红色
        self.logger.error(f"{self.name}正在执行")

        # WARNING(30) ≥ INFO(20) → 会显示，黄色
        self.logger.warning(f"{self.name}warning")

        # ── 父类工具方法演示 ─────────────────────────────────────────────
        # log_step 是父类提供的，内部还是走 self.logger.info。
        # 显示形如：... - import.node_test - INFO - [MCP查询] 开始执行
        self.log_step("MCP查询", "开始执行")

        # 返回空字典：我只打日志，不改数据
        return {}


# ── 入口守卫 ─────────────────────────────────────────────────────────────────
# if __name__ == "__main__": 的含义：
#   · 直接运行这个文件   → __name__ 等于 "__main__"  → 下面的代码执行
#   · 被别人 import      → __name__ 等于模块名        → 下面的代码不执行
# 这样写，文件既能当脚本跑、又能当模块被引用（引用时不会乱打印）。
if __name__ == "__main__":

    # ── 第 1 步：先打开日志（顺序绝对不能反）─────────────────────────────
    # setup_logging 给 root 日志工具挂上输出器、把门槛设成 INFO。
    # 如果放在打日志**之后**调，之前的日志已经发出去了、没人接，直接丢弃。
    # 口诀：**先配日志，再打日志。**
    setup_logging(logging.INFO)

    # ── 第 2 步：造节点对象 ─────────────────────────────────────────────
    # TestNode() 会走父类的 __init__：拿到全局共享配置 + 取好日志工具。
    test_node = TestNode()

    # 使用 对象() 的方式相当于调用了 对象的__call__()
    # ↑ 你的笔记完全正确。补一层：LangGraph 内部就是用 node(state)
    #   这种方式跑节点的，所以"能 node(state) 调用" = "能被 LangGraph 当节点用"。
    #
    #   传入的 {"abc": 456} 是个**不符合规定的** state（缺字段、多了 abc），
    #   但完全不报错 —— 因为 ImportGraphState 只是给编辑器看的提示，
    #   运行时 Python 不做任何检查。
    test_node({"abc": 456})

    # ════════════════════════════════════════════════════════════════════
    # ⚠️ 重要：这个文件**不能**用 `python node_test.py` 直接运行！
    # ════════════════════════════════════════════════════════════════════
    # 直接运行会报：ModuleNotFoundError: No module named 'processor'
    #
    # 原因：运行脚本时，Python 只把"脚本所在的那个目录"加入模块搜索路径，
    #      而不是你敲命令时所在的目录。直接跑这个文件时，搜索路径里是
    #      nodes/ 目录，找不到项目根目录下的 processor 包。
    #
    # 正确姿势：在**项目根目录**下用 -m 参数：
    #     python -m processor.import_processor.nodes.node_test
    # -m 表示"按模块名运行"，这时 Python 把当前目录（项目根）加进搜索路径，
    # processor 就能找到了。注意 -m 后面写点分隔的模块路径、不带 .py。
    #
    # 一句话总结：
    #     **项目内部有包依赖的脚本，用 python -m 包.模块 跑；
    #       独立的单文件脚本，才用 python 脚本.py。**
    #
    # ── 实测输出（用 -m 方式跑，已验证）────────────────────────────────────
    #   2026-09-27 11:44:12 - import.node_test - INFO  - --- node_test 开始啦 ---
    #   2026-09-27 11:44:12 - import.node_test - ERROR - node_test正在执行
    #   2026-09-27 11:44:12 - import.node_test - WARNING - node_testwarning
    #   2026-09-27 11:44:12 - import.node_test - INFO  - [MCP查询] 开始执行
    #   2026-09-27 11:44:12 - import.node_test - INFO  - --- node_test 完成啦 ---
    #
    # 从输出能验证四件事：
    #   ① debug 那行**没出现** → 级别过滤生效
    #   ② 显示顺序 = 代码执行顺序，不是按级别排序
    #   ③ 每行都带 "import.node_test" → 日志工具命名生效
    #   ④ "开始啦"在最前、"完成啦"在最后 → 它们由父类 __call__ 打的，
    #      业务日志被夹在中间 —— 这就是"父类管外壳、子类管干活"的直观体现
