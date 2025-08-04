from pathlib import Path

import nonebot
from nonebot import get_plugin_config
from nonebot.plugin import PluginMetadata

from .config import Config

__plugin_meta__ = PluginMetadata(
    name="毛五",
    description="",
    usage="",
    config=Config,
)

config = get_plugin_config(Config)

sub_plugins = nonebot.load_plugins(
    str(Path(__file__).parent.joinpath("plugins").resolve())
)

from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, Message, MessageSegment, MessageEvent, GroupMessageEvent, PrivateMessageEvent
from nonebot.params import CommandArg
from nonebot.rule import to_me
from nonebot.exception import FinishedException
import os
import random
import tempfile
from PIL import Image, UnidentifiedImageError


        
        


# 配置区域
IMAGE_DIR = "D:\qqbot\cangyao\src\maomao"  # 修改为你的图片目录
WATERMARK_PATH = "D:\qqbot\cangyao\src\watermark"  # 水印图片路径（透明底PNG最佳）
RANDOM_TEXTS = [
    "是谁家毛毛如此可爱~",
    "好想让人上前摸一摸呢",
    "随机掉落一张毛图~",
    "新鲜出炉的毛图请查收！",
    "来一张随机毛图放松一下~",
    "今日毛图图片已生成！"
]

send_random_pic = on_command("随机毛五", aliases={"maomao"}, priority=5, block=True)

@send_random_pic.handle()
async def handle_random_pic(bot: Bot, event: MessageEvent, arg: CommandArg = CommandArg()):
    # 前置检查：目录存在性
    if not os.path.exists(IMAGE_DIR):
        await send_random_pic.finish(f"图片目录不存在：{IMAGE_DIR}")
    if not os.path.isdir(IMAGE_DIR):
        await send_random_pic.finish(f"路径不是文件夹：{IMAGE_DIR}")
    
    # 前置检查：图片文件存在
    supported_formats = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp')
    image_files = [
        f for f in os.listdir(IMAGE_DIR)
        if f.lower().endswith(supported_formats) and os.path.isfile(os.path.join(IMAGE_DIR, f))
    ]
    if not image_files:
        await send_random_pic.finish("图片目录中没有可用图片~")
    
    # 选择图片并发送
    selected_img = random.choice(image_files)
    img_name = os.path.splitext(selected_img)[0]
    random_text = random.choice(RANDOM_TEXTS)
    image_path = os.path.abspath(os.path.join(IMAGE_DIR, selected_img))
    
    # 核心发送逻辑：使用 try-except 包裹
    try:
        # 构建消息
        message = Message(f"{random_text}\n{img_name}\n") + MessageSegment.image(file=image_path)
        
        # 发送消息（根据场景选择群聊/私聊）
        if isinstance(event, GroupMessageEvent):
            await bot.send_group_msg(group_id=event.group_id, message=message)
        else:
            await bot.send_private_msg(user_id=event.user_id, message=message)
        
        # 发送成功后终止事件（仅调用一次）
        await send_random_pic.finish()
    
    # 捕获特定异常并处理
    except FinishedException:
        # 忽略已终止的异常（避免重复处理）
        pass
    except Exception as e:
        # 处理其他异常（如文件损坏、权限问题）
        print(f"图片发送失败：{str(e)}")
        await send_random_pic.finish(f"图片发送失败：{str(e)[:30]}")