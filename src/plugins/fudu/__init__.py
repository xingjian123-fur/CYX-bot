from pathlib import Path

import nonebot
from nonebot import get_plugin_config
from nonebot.plugin import PluginMetadata

from .config import Config

__plugin_meta__ = PluginMetadata(
    name="fudu",
    description="",
    usage="",
    config=Config,
)

config = get_plugin_config(Config)

sub_plugins = nonebot.load_plugins(
    str(Path(__file__).parent.joinpath("plugins").resolve())
)

import time
import random
from collections import defaultdict
from nonebot import on_message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, Message
from nonebot.rule import Rule

# 存储群消息记录：{群ID: [(消息内容, 时间戳), ...]}
# 仅保留最近3条消息，用于检测连续重复
group_message_records = defaultdict(list)

# 检查是否满足连续3条相同消息的规则
async def repeat_rule(event: GroupMessageEvent) -> bool:
    group_id = event.group_id
    # 获取消息纯文本（忽略格式，仅比较内容）
    message = event.get_plaintext().strip()
    # 过滤空消息
    if not message:
        return False
    
    # 获取当前群的消息记录
    group_messages = group_message_records[group_id]
    
    # 移除30秒前的过期消息（避免长时间间隔的重复被误判）
    now = time.time()
    group_messages[:] = [msg for msg in group_messages if now - msg[1] <= 30]
    
    # 添加当前消息到记录（只保留最近3条，节省内存）
    group_messages.append((message, now))
    if len(group_messages) > 3:
        group_messages.pop(0)  # 只保留最近3条
    
    # 检查是否连续3条消息内容相同
    return len(group_messages) == 3 and all(msg[0] == message for msg in group_messages)

# 创建消息处理器（block=False确保不影响其他插件）
message_matcher = on_message(rule=Rule(repeat_rule), priority=5, block=False)

@message_matcher.handle()
async def handle_repeat_message(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id
    # 获取原始消息（保留格式，如图片、表情等）
    original_message = event.get_message()
    
    # 5%概率阻止复读
    if random.randint(1, 100) <= 5:
        await bot.send(
            event=event,
            message=Message(f"[CQ:at,qq={event.user_id}] 不准复读~")
        )
    else:
        # 发送相同内容（保留原始格式）
        await bot.send(
            event=event,
            message=original_message
        )