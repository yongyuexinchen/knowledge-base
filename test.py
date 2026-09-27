from dataclasses import dataclass, field
from typing import Set, Optional, Tuple
import os
from dotenv import load_dotenv



@dataclass
class ImportConfig:
    max_content_length: int = 2000

    @classmethod
    def from_env(cls):
        obj = cls()                 # ← 注意是 cls()，不是 ImportConfig()
        obj.max_content_length = 999
        return obj

@dataclass
class TestConfig(ImportConfig):
    debug: bool = True

c = TestConfig.from_env()
print(type(c))          # <class '__main__.TestConfig'>  ← 造出来的是子类！
print(c.debug)          # True