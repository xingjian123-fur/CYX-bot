from pathlib import Path

import nonebot
from nonebot import get_plugin_config
from nonebot.plugin import PluginMetadata

from .config import Config

__plugin_meta__ = PluginMetadata(
    name="tips",
    description="",
    usage="",
    config=Config,
)

config = get_plugin_config(Config)

sub_plugins = nonebot.load_plugins(
    str(Path(__file__).parent.joinpath("plugins").resolve())
)


from nonebot import get_driver, logger
from nonebot.adapters import Bot, Event
from nonebot.message import run_postprocessor
from nonebot.adapters.onebot.v11 import Message, MessageSegment
import random
import ast

# 适配Pydantic配置
try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseSettings

# 插件配置模型
class Config(BaseSettings):
    random_suffixes: list[str] = []  # 随机后缀列表

    if hasattr(BaseSettings, "model_config"):
        model_config = {"extra": "ignore"}
    else:
        class Config:
            extra = "ignore"

# 加载配置（添加格式容错处理）
global_config = get_driver().config
try:
    # 从全局配置获取原始值
    raw_suffixes = getattr(global_config, "random_suffixes", [])
    
    # 容错处理：如果是字符串，尝试用ast解析为列表
    if isinstance(raw_suffixes, str):
        logger.warning(f"检测到配置格式可能不正确，尝试自动修复: {raw_suffixes}")
        # 尝试解析字符串为列表（处理用户可能误加的引号）
        raw_suffixes = ast.literal_eval(raw_suffixes)
    
    # 验证是否为列表
    if not isinstance(raw_suffixes, list):
        raise ValueError(f"配置格式错误，应为列表，实际为: {type(raw_suffixes)}")
    
    # 初始化配置
    plugin_config = Config(random_suffixes=raw_suffixes)
    logger.info(f"随机后缀插件加载成功，可用后缀: {plugin_config.random_suffixes}")
except Exception as e:
    logger.error(f"配置加载失败: {str(e)}，将使用默认空列表")
    plugin_config = Config()

def get_random_suffix() -> str:
    """获取随机后缀"""
    if not plugin_config.random_suffixes:
        return ""
    return random.choice(plugin_config.random_suffixes)

@run_postprocessor
async def add_random_suffix(bot: Bot, event: Event, response: Message | str | None = None):
    """添加随机后缀到消息"""
    if not response:
        return

    # 统一转换为Message类型
    if isinstance(response, str):
        response = Message(response)
    if not isinstance(response, Message):
        return

    # 提取文本内容，确保有文字才添加后缀
    if not response.extract_plain_text():
        return

    suffix = get_random_suffix()
    if suffix:
        try:
            response.append(MessageSegment.text(suffix))
            logger.debug(f"已添加后缀: {suffix}")
        except Exception as e:
            logger.error(f"添加后缀失败: {e}")

__plugin_meta__ = {
    "name": "随机后缀添加器",
    "description": "兼容配置格式错误的随机后缀插件",
    "version": "2.0.0",
    "author": "Your Name",
    "supported_adapters": ["onebot.v11"],
    "priority": 10
}
    
