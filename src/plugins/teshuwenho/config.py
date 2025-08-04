from pydantic import BaseModel


class Config(BaseModel):
    """Plugin Config Here"""



from typing import List
from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from pathlib import Path

class Config(BaseSettings):
    qq_regex: str = r'^[1-9]\d{4,10}$'
    img_store_path: str = "data/qq_images/"
    img_suffixes: List[str] = [".png", ".jpg", ".jpeg", ".gif"]
    preset_users: List[str] = ["3152382634", "1465897544", "2580966075"]  # 替换为实际预设QQ号

    model_config = ConfigDict(extra="allow")  # 允许全局配置有额外字段

    def __init__(self, **data):
        super().__init__(** data)
        Path(self.img_store_path).mkdir(parents=True, exist_ok=True)