from pathlib import Path
import nonebot
from nonebot import get_plugin_config
from nonebot.plugin import PluginMetadata
from .config import Config


__plugin_meta__ = PluginMetadata(
    name="tswh",
    description="",
    usage="",
    config=Config,
)

config = get_plugin_config(Config)

sub_plugins = nonebot.load_plugins(
    str(Path(__file__).parent.joinpath("plugins").resolve())
)


import logging
from pathlib import Path
import nonebot
from nonebot import get_plugin_config, get_driver, on_command
from nonebot.plugin import PluginMetadata
from nonebot.matcher import Matcher
from nonebot.message import run_preprocessor
from nonebot.typing import T_Handler
from nonebot.adapters import Bot, Event
from nonebot.adapters.onebot.v11 import MessageSegment, Event as OneBotEvent, NoticeEvent

# 配置日志记录
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

__plugin_meta__ = PluginMetadata(
    name="tswh",
    description="",
    usage="",
    config=Config,
)

config = get_plugin_config(Config)

# 获取当前插件目录
PLUGIN_DIR = Path(__file__).parent.resolve()

# 解析配置（确保路径为绝对路径）
try:
    plugin_config = Config(**get_driver().config.dict())
    
    # 确保图片存储路径是绝对路径
    IMG_STORE = Path(plugin_config.img_store_path)
    if not IMG_STORE.is_absolute():
        IMG_STORE = (PLUGIN_DIR / IMG_STORE).resolve()
        logging.info(f"将图片存储路径转换为绝对路径: {IMG_STORE}")
        
    # 创建存储目录（如果不存在）
    IMG_STORE.mkdir(parents=True, exist_ok=True)
    
except Exception as e:
    logging.error(f"Failed to parse plugin configuration: {e}")
    raise

# 配置参数
SUPPORTED_SUFFIXES = plugin_config.img_suffixes
PRESET_USERS = plugin_config.preset_users


# -------------------------- 工具函数 --------------------------
def get_user_qq(event: Event) -> str | None:
    """获取用户QQ号"""
    try:
        # 只处理有user_id属性的事件（如消息事件）
        if hasattr(event, "user_id"):
            return str(event.user_id)
        return None
    except Exception as e:
        logging.error(f"Failed to get user QQ: {e}")
        return None


def find_qq_image(qq: str) -> Path | None:
    """查找本地图片，返回Path对象"""
    try:
        if not IMG_STORE.exists():
            logging.warning(f"图片存储目录不存在: {IMG_STORE}")
            return None
            
        for suffix in SUPPORTED_SUFFIXES:
            img_path = IMG_STORE / f"{qq}{suffix}"
            if img_path.exists():
                return img_path
        return None
    except Exception as e:
        logging.error(f"Failed to find QQ image: {e}")
        return None


def to_absolute_path(path: str | Path) -> Path:
    """确保路径是绝对路径"""
    if not isinstance(path, Path):
        path = Path(path)
        
    if not path.is_absolute():
        return (PLUGIN_DIR / path).resolve()
        
    return path


# -------------------------- 前置处理器（添加事件类型过滤） --------------------------
async def qq_img_pre_middleware(matcher: Matcher, bot: Bot, event: Event):
    """前置处理器：只处理消息事件，忽略其他类型事件"""
    # 检查是否为消息事件
    if not isinstance(event, OneBotEvent) or event.get_type() != "message":
        logging.debug(f"忽略非消息事件: {event.get_type()}")
        return
        
    user_qq = get_user_qq(event)
    if not user_qq or user_qq not in PRESET_USERS:
        return  # 非预设用户不处理

    # 查找图片
    img_path = find_qq_image(user_qq)
    if img_path:
        try:
            # 使用绝对路径生成URI
            file_uri = img_path.as_uri()
            logging.info(f"发送图片: {file_uri}")
            
            # 构造图片消息段
            image_message = MessageSegment.image(file_uri)
            
            # 发送图片
            await bot.send(
                event=event,
                message=image_message,
                at_sender=False
            )
        except Exception as e:
            logging.error(f"发送图片失败: {e}")
            await bot.send(event=event, message="图片发送失败，请稍后再试")


# 注册为前置处理器
run_preprocessor(qq_img_pre_middleware)


# -------------------------- 测试指令 --------------------------
test_cmd = on_command("测试", priority=5, block=True)


@test_cmd.handle()
async def handle_test():
    try:
        # 测试发送本地图片
        test_img_path = to_absolute_path("test_images/test.png")
        
        if test_img_path.exists():
            file_uri = test_img_path.as_uri()
            image_message = MessageSegment.image(file_uri)
            await test_cmd.send(message=image_message)
        
        await test_cmd.finish("测试指令执行成功")
    except Exception as e:
        logging.error(f"处理测试指令失败: {e}")
        await test_cmd.finish("测试指令执行失败")