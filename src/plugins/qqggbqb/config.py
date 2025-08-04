from pydantic import BaseModel


class Config(BaseModel):
    """Plugin Config Here"""


from pydantic import BaseModel, Field
from pathlib import Path

class Config(BaseModel):
    # 图片文件夹路径
    image_folder: Path = Field(default=Path("images"), description="图片存放文件夹路径")
    # 降低后的图片宽度（高度按比例计算）
    resized_width: int = Field(default=600, description="调整后的图片宽度")
    # 可以添加发送目标配置，例如特定群聊列表
    # target_groups: list[int] = Field(default=[], description="目标群聊列表")