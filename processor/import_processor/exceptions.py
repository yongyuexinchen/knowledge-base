# processor/import_processor/exceptions.py

r"""
项目自己的错误类型：出错时，让错误"说清楚是谁、在哪出的"
================================================================================
它不碰 state，不管数据加工。它管的是第三条线：**错误信息怎么传**。

    子类 process() 里出错（比如 raise MilvusError("连不上")）
        → BaseNode.__call__ 的 except 接住
        → 包装成 ImportProcessError（附上节点名）再往上抛
        → 上层 catch 后：从 e.node_name 知道是哪个节点挂的

state 和异常是两条平行的通道：state 传正常数据，异常传错误信息。

【为什么不直接用 Python 自带的 ValueError / RuntimeError？】
    1. 好认：上层 catch ImportProcessError 就知道"这是本项目流程里的错"，
       不会误吞 Python 自身的错误（比如语法错、内存错）。
    2. 能带信息：自带异常只能带一句话；自定义的能带上节点名、字段名，
       日志和页面提示可以直接用。
    3. 能分类：配置错 / 文件错 / 向量库错 / 对象存储错……
       不同类别可以有不同的处理方式（比如向量库错就重试）。

【这个文件里的类，谁是谁的爹】
                          Exception（Python 自带）
                               │
                    ImportProcessError          ← 所有自定义错误的总爹
      ┌────────────┬─────────────┼──────────────┬────────────┐
 StateFieldError  ConfigurationError  FileProcessingError  DocumentSplitError ...
                                      ├── PdfConversionError
                                      └── ImageProcessingError
                                                      StorageError
                                                      ├── MilvusError
                                                      └── MinioError

  规律：越往下越具体。上层可以粗线条 catch 总爹，想精细处理就 catch 具体子类。
  名词查手册：为什么自定义异常 → docs/CONCEPTS.md §11
"""


# 类名后面的 (Exception) 表示"继承自 Python 自带的错误类型"。
# 继承之后：这个类能被 raise、能被 except 接住，
# 同时又能被 except ImportProcessError 精准命中，不会误伤别的错误。
class ImportProcessError(Exception):
    """
    所有自定义错误的总爹。BaseNode.__call__ 用它包装节点里抛出的任何错误。

    它身上带三样东西：
        message   错误的一句话描述，如 "连不上 Milvus"
        node_name 哪个节点挂的，如 "node_import_milvus"
        cause     原始错误对象（保留根因）

    谁造它：BaseNode.__call__ 的 except 块。
    谁接它：LangGraph 或上层业务代码，典型写法：
        try:
            app.invoke(state)
        except ImportProcessError as e:
            print(f"{e.node_name} 挂了：{e}")
    """

    def __init__(self, message: str, node_name: str = "", cause: Exception = None):
        """
        造一个错误对象。

        输入：
            message   : 抛错的人写的一句话
            node_name : BaseNode.__call__ 传的节点名
            cause     : BaseNode.__call__ 传的原始错误对象

        加工：
            1. 把 node_name / cause 挂到对象上（给接错的人读取）
            2. 调 super().__init__(message)，让自带的 Exception 记住那句话

        输出：一个错误对象，接错的人可以读 e.node_name 和 e.cause。

        ⚠️ 类型标注小瑕疵：cause 标注说必须是 Exception，默认值却是 None，
           自相矛盾。规范写法是 cause: Optional[Exception] = None。
           不影响运行，只是标注不严谨。
        """
        # 挂在对象上，接错的人就能读出来：
        #     except ImportProcessError as e:
        #         print(e.node_name)   # 知道是哪个节点挂的
        self.node_name = node_name
        self.cause = cause

        # 关键一行：把 message 交给父类 Exception 存起来。
        # 不调这行，str(错误对象) 会是空的，日志里什么都看不到。
        # 这就是"重写 __init__ 几乎总要调一句 super().__init__()"的原因。
        super().__init__(message)

    def __str__(self):
        r"""
        规定"print(错误对象)"时显示什么。

        输入：无参数。用对象自己身上的三样东西：node_name / args / cause
             （args 是父类 Exception 存 message 的地方）

        加工：拼成一句话 "[节点名] 错误消息 (原因: 原始错误)"
             没有节点名就省掉第一段（避免打出 "[] xxx" 这种空括号），
             没有原始错误就省掉第三段。

        输出：一个字符串。用在日志、终端打印、页面错误提示。

        为什么要重写它：默认只会显示 message 一句话，
        这里想把节点名和原始错误一起带上，一行日志就够定位问题。
        """
        # 先把零件攒进列表，最后一并拼接（比反复用 + 拼字符串快，
        # 因为字符串不可变，每拼一次都要新建一个）
        parts = []

        if self.node_name:
            parts.append(f"[{self.node_name}]")

        # super().__str__() 就是父类的版本 —— 返回 message 原文
        parts.append(super().__str__())

        if self.cause:
            parts.append(f"(原因: {self.cause})")

        return " ".join(parts)


class StateFieldError(ImportProcessError):
    """
    状态字段错误：从 state 读必需字段时，发现它缺失 / 为空 / 类型不对。
    最典型的触发场景：节点顺序配错了（比如 ④ 还没跑，就去读 chunks）。

    比总爹多带两样信息：
        field_name    出问题的字段名，如 "import_file_path"
        expected_type 期望的类型，如 str

    典型用法：
        path = state.get("import_file_path")
        if not path:
            raise StateFieldError(node_name=self.name,
                                  field_name="import_file_path",
                                  expected_type=str)
        # str(e) 得到："[node_entry] 状态字段 'import_file_path' 缺失或无效，期望类型: str"
    """

    def __init__(
            self,
            node_name: str = "",        # 出错的节点
            field_name: str = "",       # 出问题的字段名
            expected_type: type = None, # 期望的类型（默认不校验类型）
            message: str = "",          # 自定义错误语，留空则自动生成
            cause: Exception = None,    # 原始错误
    ):
        """
        造一个"字段有问题"的错误。

        输入：全部由抛错的那个节点提供，最少只需给 node_name + field_name。

        加工：
            1. 把 field_name / expected_type 挂到对象上
            2. 调用方没给 message 就自动生成一句：
                   "状态字段 'xxx' 缺失或无效，期望类型: str"
            3. 剩下的（存 message / node_name / cause）交给父类处理

        输出：错误对象，比父类多两个可读属性 e.field_name / e.expected_type
        """
        self.field_name = field_name
        self.expected_type = expected_type

        # 调用方懒得写错误语时，自动拼一句像样的
        if not message:
            message = f"状态字段 '{field_name}' 缺失或无效"

            # expected_type 是类型对象（比如 str 本身），
            # 它的 __name__ 才是字符串 "str"。
            # 直接拼会打出 "<class 'str'>"，太丑。
            if expected_type:
                message += f"，期望类型: {expected_type.__name__}"

        # 用关键字参数（message= 这种写法）调父类，
        # 因为父类的参数顺序和这里不一样，按位置传会传错
        super().__init__(message, node_name=node_name, cause=cause)


# ── 下面全是"空壳子类"：方法体只有 pass ──────────────────────────────────────
# 看起来像废话，但价值是**给错误分类起名**。
# 有了名字，上层就能精准接某一类错：
#     try:
#         ...
#     except MilvusError:      # 只处理向量库的错，别的错继续往上抛
#         ...
# 反例：全都抛 ImportProcessError，就分不清"是向量库挂了还是 MinIO 挂了"。
#
# 【谁抛它们】对照表（类名后面标了会用到它的节点）：
#     ConfigurationError    ← 任何节点发现配置缺必需值时
#     FileProcessingError   ← ②③ 文件读写出问题时
#     PdfConversionError    ← ② MinerU 解析 PDF 失败
#     ImageProcessingError  ← ③ 图片处理 / 上传失败
#     DocumentSplitError    ← ④ 切分逻辑异常
#     EmbeddingError        ← ⑥ 向量模型调用失败
#     LLMError              ← ③⑤ 大模型超时 / 限流 / 答非所问
#     StorageError          ← ⑦ 存储类错误的总爹（一般不直接抛它）
#     MilvusError           ← ⑦ 向量库操作失败
#     MinioError            ← ⑦ 对象存储操作失败
#     ValidationError       ← ① 文件格式不支持之类的输入校验失败


class ConfigurationError(ImportProcessError):
    """配置错误：环境变量缺失或配置值无效"""
    pass  # 空类体必须写 pass，否则语法错误（Python 靠缩进划分代码块，不能什么都不写）


class FileProcessingError(ImportProcessError):
    """文件处理错误：文件不存在、格式错误、读写失败"""
    pass


class PdfConversionError(FileProcessingError):
    """
    PDF 转换错误：MinerU 转换失败。

    注意这是"多级继承"：PdfConversionError → FileProcessingError → ImportProcessError。
    好处：catch FileProcessingError 能一次接住 PDF 转换和图片处理两类错；
          catch PdfConversionError 则只接 PDF 这一类。粗细自己挑。
    """
    pass


class ImageProcessingError(FileProcessingError):
    """图片处理错误：图片总结、上传失败"""
    pass


class DocumentSplitError(ImportProcessError):
    """文档切分错误：切分逻辑异常"""
    pass


class EmbeddingError(ImportProcessError):
    """向量化错误：模型调用失败、向量生成异常"""
    pass


class LLMError(ImportProcessError):
    """大模型调用错误：API 调用失败、响应解析失败"""
    pass


class StorageError(ImportProcessError):
    """存储错误：数据库操作失败（一般不直接抛它，抛下面两个更具体的）"""
    pass


class MilvusError(StorageError):
    """Milvus 存储错误（向量库）"""
    pass


class MinioError(StorageError):
    """MinIO 存储错误（对象存储）"""
    pass


# ── 一个设计缺口 ─────────────────────────────────────────────────────────────
# 有 MilvusError（向量库）、MinioError（对象存储），
# 但 .env 里明明还配了 MongoDB，却没有 MongoError。
# 将来写 ⑦ 的"元数据入库"时，建议补一个 class MongoError(StorageError)。
class ValidationError(ImportProcessError):
    """数据验证错误：输入数据不符合预期（如文件格式不支持）"""
    pass
