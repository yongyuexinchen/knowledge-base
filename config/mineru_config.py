from dataclasses import dataclass
import os
from dotenv import load_dotenv

#1.加载配置文件
load_dotenv()

@dataclass
class MinerUConfig:
    # 键名必须和 .env 里的一致 —— .env 里写的是 MINERU_URL / MINERU_TOKEN
    # （不带 .env 直接跑时给空串兜底，由节点启动时的配置校验报明确的错）
    base_url_prod: str
    api_token_prod: str
    base_url_test: str
    api_token_test: str

mineru_config = MinerUConfig(
    base_url_prod=os.getenv("MINERU_URL", ""),
    api_token_prod=os.getenv("MINERU_TOKEN", ""),
    base_url_test="test",
    api_token_test="test"
)




