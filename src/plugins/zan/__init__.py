from pathlib import Path

import nonebot
from nonebot import get_plugin_config
from nonebot.plugin import PluginMetadata

from .config import Config

__plugin_meta__ = PluginMetadata(
    name="zan",
    description="",
    usage="",
    config=Config,
)

config = get_plugin_config(Config)

sub_plugins = nonebot.load_plugins(
    str(Path(__file__).parent.joinpath("plugins").resolve())
)



from nonebot import on_command, on_fullmatch
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, GroupMessageEvent, Message, MessageSegment
from nonebot.params import CommandArg
from nonebot.rule import to_me
from nonebot.permission import SUPERUSER
from nonebot.log import logger
import asyncio
import random
import re

# 插件配置
MAX_LIKE_COUNT = 10  # 单次最大点赞数
MIN_DELAY = 1  # 点赞间隔最小时间(秒)
MAX_DELAY = 3  # 点赞间隔最大时间(秒)

# 指令定义
like_me = on_fullmatch(("赞我", "点赞我", "名片赞"), priority=5, block=True)
like_other = on_command("赞他", priority=5, block=True)
set_like_count = on_command("设置赞数", permission=SUPERUSER, priority=5, block=True)

# 全局变量存储最大点赞数
global_max_like = MAX_LIKE_COUNT

async def send_like(bot: Bot, user_id: int, count: int) -> bool:
    """发送名片赞"""
    try:
        # 循环发送点赞请求
        for i in range(count):
            # 调用 OneBot 点赞 API
            await bot.send_like(user_id=user_id, times=1)
            logger.info(f"给用户 {user_id} 发送第 {i+1} 个赞")
            
            # 随机延迟，避免被风控
            if i < count - 1:  # 最后一次不需要延迟
                delay = random.uniform(MIN_DELAY, MAX_DELAY)
                await asyncio.sleep(delay)
                
        return True
    except Exception as e:
        logger.error(f"点赞失败: {str(e)}")
        return False

def extract_qq_from_message(message: Message) -> int:
    """从消息中提取QQ号（优先提取@的用户，再提取文本中的QQ号）"""
    # 提取@的用户
    for segment in message:
        if segment.type == "at" and segment.data.get("qq"):
            return int(segment.data["qq"])
    
    # 从文本中提取QQ号（纯数字）
    text = message.extract_plain_text().strip()
    qq_match = re.search(r"\b\d{5,13}\b", text)  # QQ号通常为5-13位数字
    if qq_match:
        return int(qq_match.group())
    
    return None

@like_me.handle()
async def handle_like_me(bot: Bot, event: MessageEvent):
    """赞自己"""
    user_id = event.user_id
    await like_me.send(f"正在给你点赞 {global_max_like} 次，请稍候...")
    
    success = await send_like(bot, user_id, global_max_like)
    if success:
        await like_me.finish(f"已成功为你点赞 {global_max_like} 次！")
    else:
        await like_me.finish("点赞过程中出现错误，请稍后再试~")

@like_other.handle()
async def handle_like_other(bot: Bot, event: MessageEvent, arg: Message = CommandArg()):
    """赞指定用户，支持两种方式：
    1. @机器人 赞他 @目标用户 [次数]
    2. @机器人 赞他 QQ号 [次数]
    """
    # 提取目标用户QQ号
    target_id = extract_qq_from_message(arg)
    if not target_id:
        await like_other.finish("请@目标用户或输入QQ号，格式：\n赞他 @用户 [次数]\n赞他 123456 [次数]")
        return
    
    # 提取点赞次数（可选参数）
    text = arg.extract_plain_text().strip()
    count = global_max_like  # 默认使用全局最大次数
    
    # 尝试从文本中提取次数
    try:
        # 分割文本并取最后一个数字作为次数
        parts = text.split()
        for part in reversed(parts):
            if part.isdigit():
                num = int(part)
                if 1 <= num <= global_max_like:
                    count = num
                    break
    except:
        pass  # 提取失败则使用默认值
    
    await like_other.send(f"正在给 {target_id} 点赞 {count} 次，请稍候...")
    success = await send_like(bot, target_id, count)
    
    if success:
        await like_other.finish(f"已成功给 {target_id} 点赞 {count} 次！")
    else:
        await like_other.finish("点赞过程中出现错误，请稍后再试~")

@set_like_count.handle()
async def handle_set_count(arg: Message = CommandArg()):
    """设置单次最大点赞数（仅管理员）"""
    global global_max_like
    count_str = arg.extract_plain_text().strip()
    
    if not count_str:
        await set_like_count.finish(f"当前单次最大点赞数：{global_max_like}，设置格式：设置赞数 10")
        return
        
    try:
        new_count = int(count_str)
        if new_count < 1 or new_count > 100:
            await set_like_count.finish("赞数范围应为1-100")
            return
            
        global_max_like = new_count
        await set_like_count.finish(f"已设置单次最大点赞数为：{global_max_like}")
    except ValueError:
        await set_like_count.finish("请输入数字，格式：设置赞数 10")


