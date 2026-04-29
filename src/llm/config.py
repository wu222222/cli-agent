import os
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


@dataclass
class LLMConfig:
    api_key: Optional[str] = field(default_factory=lambda: os.getenv("DASHSCOPE_API_KEY", None))
    base_url: str = field(default_factory=lambda: os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"))
    model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", None))
    temperature: float = 0.3
    max_tokens: int = 2048
    timeout: int = 60

    def __post_init__(self):
        
        if self.api_key is None:
            self.api_key = os.getenv("DASHSCOPE_API_KEY", "")

        if not self.api_key:
            raise ValueError("API Key 未设置，请设置 DASHSCOPE_API_KEY 环境变量")

        if self.model is None:
            raise ValueError("模型 未设置，请设置 LLM_MODEL 环境变量")

    @classmethod
    def from_env(cls) -> "LLMConfig":
        return cls()
