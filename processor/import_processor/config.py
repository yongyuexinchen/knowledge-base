# processor/import_processor/config.py

r"""
配置管理：项目里所有"可以调的参数"都集中在这一个文件
================================================================================
它不碰 state，不管数据加工。它管的是另一条线：**配置从哪来**。

    .env 文件 ──load_dotenv──▶ 环境变量 ──os.getenv──▶ ImportConfig 对象
                                                              │ get_config() 全局共享一份
                                                              ▼
                                        各节点 __init__ 里 self.config = ...
                                                              ▼
                                        process() 里 self.config.xxx 读参数

为什么要专门搞一个文件管配置，而不是在哪用就在哪 os.getenv？
    · 键名拼错时，只有跑到那一步才发现；集中一处，一眼核对
    · 想改某个参数，不用满项目找 —— 只来这个文件
    · 测试时可以传一份假配置进去，不用改真实环境变量

【这个文件里有什么】
    ImportConfig             配置对象，字段清单 = "这个项目能调什么"
    get_config()             拿全局共享的那份配置（全程序只造一次）
    ImportConfig.from_env()  从环境变量造一份新配置（和 ImportConfig() 等价）

【名词查手册】docs/CONCEPTS.md
    @dataclass 是什么                     → §7
    field(default_factory=...) 为什么必须 → §7
    @classmethod 和 cls                   → §6
    为什么配置要集中管、为什么只造一份      → §10
"""

from dataclasses import dataclass, field   # dataclass：照着字段声明自动生成构造函数，省掉手写 __init__
from typing import Set, Optional

import os

from dotenv import load_dotenv

# 读 .env 文件，把里面的键值对倒进环境变量。
# 注意两点：
#   ① 这行写在模块顶层 —— 谁 import 这个文件，谁就触发读取（"import 就有动作"）。
#      好处是无感；坏处是测试时想换配置会比较绕。
#   ② override=True 表示：.env 里的值**强制盖掉**系统里已有的同名环境变量。
#      本地开发方便；上生产要小心（.env 可能顶掉容器注入的正式配置）。
load_dotenv(override=True)


# @dataclass 的作用：Python 会扫描下面所有"字段名: 类型 = 默认值"的声明，
# 自动生成构造函数。于是 ImportConfig() 就能直接造出一个装满默认值的对象。
#
# 每个字段下面标两件事：
#   【值从哪来】写死的 / .env 里的哪个键
#   【谁读它】哪个节点用（节点编号①~⑦对应 docs/FLOW.md）
@dataclass
class ImportConfig:
    """导入流程的全部可调参数。"""

    # ==================== 文档切分参数（写死的，不走 .env）====================
    max_content_length: int = 2000
    # 【值从哪来】写死在这里。想改要改代码。
    # 【含义】单个切片的字数上限
    # 【谁读】NodeDocumentSplit ④
    # 【调它的后果】太小 → 一句话被切两半；太大 → 检索不精准、容易超模型窗口

    img_content_length: int = 200
    # 【值从哪来】写死
    # 【含义】给看图模型描述图片时，附带"图片周边文字"的长度
    # 【谁读】NodeMDImg ③
    # 【为什么要带周边文字】单看一张图容易认错场景，告诉模型上下文才贴题

    min_content_length: int = 500
    # 【值从哪来】写死
    # 【含义】切片字数下限，比这短的碎片会尝试和相邻块合并
    # 【谁读】④
    # 【为什么】标题、短段落会产生极短的块，单独做向量没信息量还白占位置

    overlap_sentences: int = 1
    # 【值从哪来】写死
    # 【含义】相邻切片之间重叠的句数（防止语义正好在切分点被切断）
    # 【谁读】④
    # 【代价】向量库略变大（约 5%~10%）

    item_name_chunk_k: int = 3
    # 【值从哪来】写死
    # 【含义】识别主体名时，只取前 K 个切片喂给大模型
    # 【谁读】NodeItemNameRecognition ⑤
    # 【为什么只看前几个】判断"这篇文档讲什么"看开头就够（标题摘要都在前面），
    #                     全文喂进去 token 成本翻十倍

    item_name_chunk_size: int = 2500
    # 【值从哪来】写死
    # 【含义】上面那 K 个切片，每个只截取前 2500 字
    # 【谁读】⑤
    # 【算账】3 × 2500 = 7500 字 ≈ 5k token，是这个任务的合理规模

    # 支持的图片扩展名
    # ── 为什么不能直接写 = {".jpg", ...} 而要包一层 field(default_factory=...)？──
    # 这是 Python 的经典坑：集合/列表/字典这类"会变的对象"如果直接写在等号后面，
    # 只会在类定义时创建一次，被所有对象共用 —— 别人加了一个，你也会跟着多一个。
    # default_factory 里放一个"无参小函数"，每次造对象都重新调一次，
    # 每个对象拿到的都是独立的新集合。（§7 有完整实验）
    image_extensions: Set[str] = field(
        # lambda 就是"临时写个匿名小函数"，这里等价于 def f(): return {...}
        default_factory=lambda: {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
    )
    # 【值从哪来】写死
    # 【谁读】③（判断扫到的是不是真图片，过滤掉链接、附件）

    # ==================== 大模型配置（从 .env 读）====================
    # 这类字段的统一写法：
    #   default_factory=lambda: os.getenv("环境变量名", "取不到时的默认值")
    # 为什么用 factory 而不是直接 = os.getenv(...)？
    #   直接写是在"类被定义那一刻"读一次；factory 是"每次造对象时"现读。
    #   测试时想换环境变量再造对象，factory 才能读到新值。
    # 为什么第二个参数（默认值）不能省？
    #   键不存在时 os.getenv 返回 None，而字段声明的类型是 str ——
    #   后面 None.xxx 就会报 AttributeError。给个空串兜底，错得明白。

    # ==================== MinerU 配置 ====================
    mineru_api_token: str = field(
        default_factory=lambda: os.getenv("MINERU_API_TOKEN", "")
    )
    mineru_base_url: str = field(
        default_factory=lambda: os.getenv("MINERU_BASE_URL", "")
    )

    openai_api_base: str = field(
        default_factory=lambda: os.getenv("OPENAI_API_BASE", "")
    )
    # 【值从哪来】.env 的 OPENAI_API_BASE
    #             实测值："https://dashscope.aliyuncs.com/compatible-mode/v1"
    # 【谁读】②③⑤ 调模型时当服务地址
    # 【说明】这是阿里云 DashScope 的"兼容 OpenAI 协议"入口，
    #        所以能用 OpenAI 的客户端库去调通义千问

    openai_api_key: str = field(
        default_factory=lambda: os.getenv("OPENAI_API_KEY", "")
    )
    # 【值从哪来】.env 的 OPENAI_API_KEY（形如 sk-xxxx）
    # 【谁读】所有调大模型的节点：②③⑤
    # ⚠️ 密钥，绝不进 Git —— .gitignore 已排除 .env

    vl_model: str = field(
        default_factory=lambda: os.getenv("VL_MODEL", "")
    )
    # 【值从哪来】.env 的 VL_MODEL
    # 【谁读】NodeMDImg ③
    # 【说明】VL = 视觉语言模型，专门"看图说话"

    item_model: str = field(
        default_factory=lambda: os.getenv("ITEM_MODEL", "")
    )
    # 【值从哪来】.env 的 ITEM_MODEL
    # 【谁读】NodeItemNameRecognition ⑤
    # 【说明】识别主体名是轻任务，可以配个便宜模型省钱

    default_model: str = field(
        default_factory=lambda: os.getenv("MODEL", "")
    )
    # 【值从哪来】.env 的 MODEL 键
    # 【谁读】将来所有"没特别指定模型"的调用
    # ⚠️⚠️ 这里有个真 bug（实测确认）：
    #      这里读的键名叫 "MODEL"，但 .env 里写的键名是 "LLM_DEFAULT_MODEL"。
    #      两边对不上 → 这个字段**永远是空字符串**，不报错、不崩溃，
    #      直到大模型调用时抛"model 参数为空"才会暴露。
    #      修法：把 "MODEL" 改成 "LLM_DEFAULT_MODEL"。

    # ==================== Milvus 配置（向量库）====================
    milvus_url: str = field(
        default_factory=lambda: os.getenv("MILVUS_URL", "")
    )
    # 【值从哪来】.env 的 MILVUS_URL
    # 【谁读】NodeImportMilvus ⑦ —— 连向量库用

    chunks_collection: str = field(
        default_factory=lambda: os.getenv("CHUNKS_COLLECTION", "")
    )
    # 【值从哪来】.env 的 CHUNKS_COLLECTION
    # 【谁读】⑦
    # 【说明】collection ≈ 数据库里的"表"。这个存"切片 + 向量"，是检索主力

    item_name_collection: str = field(
        default_factory=lambda: os.getenv("ITEM_NAME_COLLECTION", "")
    )
    # 【值从哪来】.env 的 ITEM_NAME_COLLECTION
    # 【谁读】⑦
    # 【说明】存"主体名 + 向量"，检索时先按主体粗筛、再在文档内精查

    # ==================== MinIO 配置（对象存储，放图片和文件）====================
    minio_endpoint: str = field(
        default_factory=lambda: os.getenv("MINIO_ENDPOINT", "")
    )
    # 【值从哪来】.env 的 MINIO_ENDPOINT
    # 【谁读】③⑦

    minio_access_key: str = field(
        default_factory=lambda: os.getenv("MINIO_ACCESS_KEY", "")
    )
    # 【值从哪来】.env 的 MINIO_ACCESS_KEY ⚠️ 密钥，勿入库
    # 【谁读】③⑦

    minio_secret_key: str = field(
        default_factory=lambda: os.getenv("MINIO_SECRET_KEY", "")
    )
    # 【值从哪来】.env 的 MINIO_SECRET_KEY ⚠️ 密钥，勿入库
    # 【谁读】③⑦

    minio_bucket: str = field(
        default_factory=lambda: os.getenv("MINIO_BUCKET_NAME", "")
    )
    # 【值从哪来】.env 的 MINIO_BUCKET_NAME（注意键名带 _NAME 后缀）
    # 【谁读】③⑦
    # 【说明】bucket（桶）≈ 顶层目录
    minio_img_dir: str = field(
        default_factory=lambda: os.getenv("MINIO_IMG_DIR", "")
    )

    minio_secure: bool = False
    # 【值从哪来】写死 False（不走 .env）—— 本地开发用 http 即可
    # 【谁读】下面的 get_minio_base_url()
    # 【想上 https】改这里，或者补一个从环境变量读 + 字符串转布尔的逻辑

    # ==================== 向量配置 ====================
    embedding_dim: int = field(
        default_factory=lambda: int(os.getenv("EMBEDDING_DIM", "1024"))
    )
    # 【值从哪来】.env 的 EMBEDDING_DIM，取不到就用 "1024"
    # 【谁读】⑦ 建 collection 时声明向量维度（必须和模型真实输出一致）
    # 【为什么要包一层 int()】环境变量读出来永远是字符串，不转的话
    #    拿到的是 "1024" 而不是 1024，建表时会报类型不符。
    # ⚠️⚠️ 实测冲突：.env 里 EMBEDDING_DIM=1536（对应云端模型 text-embedding-v4），
    #    而本地模型 BGE-M3 的输出是 1024 维 —— 两套向量化方案在打架：
    #       方案① 云端 text-embedding-v4 → 1536 维（省事、按量付费、要联网）
    #       方案② 本地 BGE-M3            → 1024 维（免费、要 GPU、首次加载慢）
    #    动手写⑥⑦之前必须先选定一套，让这里的值和模型维度严格一致。

    embedding_batch_size: int = 8
    # 【值从哪来】写死
    # 【谁读】NodeBGEEmbedding ⑥ —— 一次送多少条文本给模型
    # 【含义】太小跑不满 GPU；太大显存溢出。8 是保守值。
    # ⚠️ 千万别 for 循环一条条算向量，必须成批送 —— 慢一个数量级。

    # ==================== 速率限制 ====================
    requests_per_minute: int = 15
    # 【值从哪来】写死
    # 【谁读】③ —— 控制调看图模型的频率，防触发供应商限流
    # 【算账】一份 50 张图的 PDF，15 次/分钟 → 要跑 3 分多钟

    # ============================================================================
    # ⚠️ 缺口清单：.env 里配了、但这里没有对应字段的键（实测核对）
    # ============================================================================
    # 这些键躺在 .env 里却读不进来，节点想用只能自己 os.getenv 或写死，
    # "集中管配置"的意义就被破坏了。建议逐个补成字段：
    #
    #   向量相关（⑥ 必需）：
    #       BGE_M3_PATH=本地模型目录   BGE_M3=BAAI/bge-m3
    #       BGE_DEVICE=cuda:0          BGE_FP16=True
    #       EMBEDDING_MODEL=text-embedding-v4
    #       注意 BGE_FP16 的坑：os.getenv 读出来是字符串 "True"，
    #       直接 bool("False") 也会得到 True（非空字符串恒为真）！
    #       必须显式判断：
    #           bge_fp16: bool = field(
    #               default_factory=lambda: os.getenv("BGE_FP16", "").lower() in ("1", "true", "yes")
    #           )
    #
    #   Milvus 相关（⑦ 必需）：
    #       MILVUS_METRIC_TYPE=COSINE        相似度算法
    #       MILVUS_MIN_COSINE_SCORE=0.75     召回结果的相似度下限
    #
    #   其他：BGE_RERANKER_*（重排模型，架构里有规划但代码还没跟上）、
    #        MINERU_MODEL_SOURCE / MODELSCOPE_*（② 的 PDF 解析器参数）
    #
    # 👉 建议：一次性把这批键补成字段（约 12 行），写节点时就不用到处 os.getenv 了。

    # ── 你自己写的笔记，非常准确，原样保留 ─────────────────────────────────────
    # 「这里调用变为类只是"换个参数"，"实例 self"换成"类 cls"，
    #   这里返回 cls 可以，返回 self 不行。
    #   Python 只要看到"用 . 调用"，就会自动把 . 左边的东西塞进第一个参数。
    #   所以你必须声明一个参数来接它 —— 接住类，就是 @classmethod；
    #   接住对象，就是普通方法。」
    #
    # ✅ 完全正确。只补一点："返回 self 不行"的真正原因是 ——
    #    如果写死成 ImportConfig()，子类调用时造出来的还是父类对象；
    #    用 cls() 则"谁调用就造谁"：子类调用 → 造出子类对象（§6，test.py 有实验）。
    @classmethod
    def from_env(cls) -> "ImportConfig":
        """
        从环境变量造一份新配置。

        输入：无显式参数。隐藏的输入是 cls —— "谁调用就是谁"：
                ImportConfig.from_env()  → cls = ImportConfig
                TestConfig.from_env()    → cls = TestConfig（子类）

        加工：cls() —— 调自动生成的构造函数，
              每个字段各自去环境变量里取值（取不到用默认值）。

        输出：一个全新的 ImportConfig 对象，交给 get_config() 存起来共用。

        返回类型 "ImportConfig" 为什么加引号：
            写这行注解的时候，ImportConfig 这个类本身还没定义完，
            名字还不存在。加引号变成字符串，Python 就会"以后再解析"，
            这叫延迟解析。Python 3.10+ 也可以靠 from __future__ import annotations。
        """
        # cls() 不带参数：因为每个字段的默认值已经写在 field(...) 里了
        return cls()

    def get_minio_base_url(self) -> str:
        """
        拼出 MinIO 的基础地址。

        输入：无参数。用对象自己身上的两个字段：
                self.minio_secure    决定用 https:// 还是 http://
                self.minio_endpoint  形如 "127.0.0.1:9000"

        输出：一个字符串，形如 "http://127.0.0.1:9000"，给 ③⑦ 拼文件地址用。
        """
        # 三元表达式：条件为真取前面的值，否则取后面的
        protocol = "https://" if self.minio_secure else "http://"
        return protocol + f"{self.minio_endpoint}"


# ================================================================================
# 全局共享配置：全程序只造一份，所有节点用同一份
# ================================================================================
# 好处：① 读 .env 这种文件操作只做一次  ② 运行期间配置不会中途变脸。
# 做法：模块级变量 + "用到才造"（第一次调用 get_config 时才真正创建）。

# 名字前的下划线 _ 是 Python 的约定："这是模块内部用的，外人别碰"。
# 注意只是约定，不是强制。
_config: Optional[ImportConfig] = None


def get_config() -> ImportConfig:
    """
    拿全局共享的配置对象。节点 __init__ 里的 self.config 就是它。

    输入：无参数。

    加工：
        第一次调用 → 造一份配置，存进模块级变量 _config
        之后再调   → 直接返回存好的那份，不重复造

    输出：ImportConfig 对象。**同一个程序里永远返回同一个对象**，
        交给每个节点 __init__ 里的 self.config = config or get_config()。
    """

    # ── global 声明为什么必须有 ──
    # 函数里对一个变量"赋值"时，Python 默认认为你要新建一个**局部**变量。
    # 不写 global，下面的 _config = ... 就只是新建了个局部变量，
    # 模块级那个永远是 None —— 每次调用都重新读环境变量，"只造一份"就失效了。
    # 记忆：**只读不用 global，要赋值必须 global。**
    global _config

    # 第一次调用时 _config 是 None，这时才真正造对象（用到才造）
    # 用 is 而不是 ==：这里判断的是"有没有这个对象"（身份判断），
    # == 会去逐个字段比较内容，没必要。
    if _config is None:
        _config = ImportConfig.from_env()
    return _config


# ── 这个写法的已知短板（了解即可，要改时再改）────────────────────────────────
# 1. 多线程同时第一次调用，可能造出两个对象（本项目单进程流水线，暂无影响）。
# 2. 想重置只能手动 _config = None，不太优雅；规范做法是提供 reset_config()。
