# test.py
# ================================================================================
# ⚠️ 定位说明：这是学习阶段写的**试验田**，验证"@classmethod + 继承"的行为，
#    和知识库业务无关。学明白之后建议挪到 tests/ 目录，或删掉（理由见文末）。
#
# ── 本文件要证明的结论（先剧透）──────────────────────────────────────────────
#   **@classmethod 里的 cls 会跟着"调用它的那个类"走：
#     子类调用时，造出来的是子类对象，不是父类对象。**
#   这正是真实代码 config.py 里 from_env() 写 return cls()、
#   而不是写死 return ImportConfig() 的原因。
# ================================================================================

from dataclasses import dataclass, field   # field 在本文件其实没用到（从 config.py 复制来的）
import os                                   # 没用到
from dotenv import load_dotenv              # 没用到
# ↑ 三个没用的 import 说明这个文件是"复制粘贴"出来的。不影响运行。


# ── 这是 config.py 里 ImportConfig 的"简化副本" ──────────────────────────────
# ⚠️ 它和 processor/import_processor/config.py 里那个**是两个不同的类**，
#    只是名字撞了。这里怎么改都不影响正式代码 —— 但也埋了坑：
#    将来真去改配置时，可能神志不清地改错文件。
@dataclass
class ImportConfig:
    """只保留一个字段的迷你版配置，方便观察行为"""

    max_content_length: int = 2000

    # ── 本文件的核心 ─────────────────────────────────────────────────────
    @classmethod
    def from_env(cls):
        """
        工厂方法：造一个配置对象。

        输入：无显式参数。隐藏的输入是 cls —— "谁调用就是谁"：
                ImportConfig.from_env()  → cls = ImportConfig
                TestConfig.from_env()    → cls = TestConfig（子类）
            【哪来的】Python 自动塞的：用"类.方法()"调用时，
                     点号左边那个类会被塞进第一个参数。
            （本文件没有真的读环境变量，只保留了方法名，真实版在 config.py。）

        加工：
            1. cls() 造一个对象（造的是哪个类，取决于 cls 是谁）
            2. 把它的 max_content_length 强制改成 999

        输出：一个配置对象。关键：子类调用时返回的是 **TestConfig 对象**，
             不是 ImportConfig 对象。
        """
        obj = cls()                 # ← 全文件的题眼：是 cls()，不是写死的 ImportConfig()
        #   子类调用时 cls = 子类，所以造出来的是子类对象。

        # 强制把默认的 2000 改成 999，方便肉眼验证"赋值确实生效了"
        obj.max_content_length = 999
        return obj


@dataclass
class TestConfig(ImportConfig):
    """
    子类：在父类基础上多加一个字段。

    @dataclass 的继承规则：子类自动拥有父类的全部字段，自己新增的排在后面。
    所以 TestConfig 的构造参数等价于：TestConfig(max_content_length=2000, debug=True)
    """

    debug: bool = True


# ══════════════════════════════════════════════════════════════════════════════
# ⚠️⚠️ 下面三行是"模块级代码"（没有缩进、没有函数包裹）：
#      **只要 import 这个文件，它们就会立刻执行。**
# 对比 node_test.py —— 那里的调试代码包在 if __name__ == "__main__": 里，
# import 时不会执行。那才是规范写法，本文件缺了这层守卫。
# ══════════════════════════════════════════════════════════════════════════════

# 用**子类**调用**父类**定义的 from_env
c = TestConfig.from_env()

# 期望打印 <class '__main__.TestConfig'> —— 证明造出来的是子类对象
# （直接运行 python test.py 时，这个模块的名字就叫 "__main__"）
print(type(c))

# 打印 True。debug 是子类自己的字段，值来自类里的默认值。
print(c.debug)

# 可以再补一行验证（原文没写）：
#     print(c.max_content_length)   # 期望 999，证明父类的逻辑也作用到了子类对象上


# ================================================================================
# 建议处理方式（按推荐度排序）：
#   ① 挪到 tests/ 目录，改写成正式的 pytest 用例 —— 以后改 config.py 能自动验证
#   ② 直接删掉 —— 结论已经消化了
#   ③ 保留，但把上面的模块级代码包进 if __name__ == "__main__":
#
# ⚠️ 不建议维持现状：项目根目录的 test.py 和正式的 config.py 里
#    各有一个 ImportConfig，同名不同物，将来重构极易改错文件。
# ================================================================================
