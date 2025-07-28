from pathlib import Path

import nonebot
from nonebot import get_plugin_config
from nonebot.plugin import PluginMetadata

from .config import Config



__plugin_meta__ = PluginMetadata(
    name="wife",
    description="",
    usage="",
    config=Config,
)

config = get_plugin_config(Config)

sub_plugins = nonebot.load_plugins(
    str(Path(__file__).parent.joinpath("plugins").resolve())
)

import random
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from nonebot import on_command, on_notice, get_driver, get_bot
from nonebot.adapters.onebot.v11 import (
    Bot,
    GroupMessageEvent,
    MessageSegment,
    PrivateMessageEvent,
    Message
)
from nonebot.adapters.onebot.v11.event import GroupIncreaseNoticeEvent
from nonebot.log import logger

# 插件元信息
__plugin_name__ = "每日群配对"
__plugin_usage__ = "群聊中发送 '配对' 随机绑定一位群友，双方可见，每日0点重置"

# 数据存储目录
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
# 每日配对记录（每个群一个文件）
DAILY_PAIR_FILE = lambda group_id: DATA_DIR / f"daily_pairs_{group_id}.json"

# 获取今日日期（用于每日重置）
def get_today() -> str:
    return datetime.now().strftime("%Y-%m-%d")

# 初始化每日配对数据
def init_daily_pairs(group_id: str) -> Dict:
    """格式: {日期: {用户ID: 配对用户ID}}"""
    file = DAILY_PAIR_FILE(group_id)
    if file.exists():
        try:
            with open(file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载群 {group_id} 配对数据失败: {e}，拿着截屏去扇星见吧")
    return {}

# 保存每日配对数据
def save_daily_pairs(group_id: str, data: Dict):
    file = DAILY_PAIR_FILE(group_id)
    try:
        with open(file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"保存群 {group_id} 配对数据失败: {e}，拿着截屏去扇星见吧")

# 获取并验证群成员列表（跳过错误用户）
async def get_valid_group_members(bot: Bot, group_id: int) -> List[Dict]:
    """获取群成员列表并过滤掉无法获取信息的用户"""
    try:
        # 获取群成员基本列表（可能包含已退群或异常用户）
        members = await bot.get_group_member_list(group_id=group_id)
        
        valid_members = []
        for member in members:
            user_id = member["user_id"]
            # 跳过机器人自身
            if user_id == bot.self_id:
                continue
                
            # 直接使用列表中的信息，不额外调用API
            valid_members.append({
                "user_id": user_id,
                "nickname": member["nickname"],
                "card": member["card"] or member["nickname"],
                "avatar": f"https://q1.qlogo.cn/g?b=qq&nk={user_id}&s=640"
            })
                
        return valid_members
    except Exception as e:
        logger.error(f"获取群 {group_id} 成员列表失败: {e}，拿着截屏去扇星见吧")
        return []

# 获取今日配对（不存在则生成，增强错误处理）
async def get_or_generate_pair(bot: Bot, group_id: int, user_id: int) -> Optional[int]:
    today = get_today()
    pairs = init_daily_pairs(str(group_id))
    
    # 确保今日数据存在
    if today not in pairs:
        pairs[today] = {}
        save_daily_pairs(str(group_id), pairs)
    
    # 检查当前用户是否已有配对
    if str(user_id) in pairs[today]:
        return pairs[today][str(user_id)]
    
    # 循环尝试获取可用配对（最多尝试3次，防止无限循环）
    for attempt in range(3):
        # 获取有效成员列表
        valid_members = await get_valid_group_members(bot, group_id)
        
        # 过滤掉已配对和自己
        available_members = [
            m for m in valid_members 
            if str(m["user_id"]) not in pairs[today] and m["user_id"] != user_id
        ]
        
        # 没有可用成员时返回None
        if not available_members:
            return None
        
        # 随机选择一个配对对象
        partner = random.choice(available_members)
        partner_id = partner["user_id"]
        
        # 保存双向配对关系
        pairs[today][str(user_id)] = partner_id
        pairs[today][str(partner_id)] = user_id
        save_daily_pairs(str(group_id), pairs)
        
        return partner_id
    
    logger.error(f"用户 {user_id} 配对尝试多次失败，拿着截屏去扇星见吧")
    return None

# 插件启动初始化
async def startup_init():
    """启动时无需特殊初始化"""
    logger.info("每日群配对插件已加载")

get_driver().on_startup(startup_init)

# 新成员入群处理
welcome_handler = on_notice(priority=10, block=True)

@welcome_handler.handle()
async def handle_new_member(bot: Bot, event: GroupIncreaseNoticeEvent):
    group_id = event.group_id
    # 发送欢迎消息
    welcome_msg = (
        MessageSegment.at(event.user_id) + 
        " 欢迎加入本群！🎉\n"
        "（啃啃新人~）"
    )
    await welcome_handler.send(welcome_msg)

# 获取用户信息（从已缓存的成员列表中查找）
def get_user_info(member_list: List[Dict], user_id: int) -> Dict:
    """从已缓存的成员列表中查找用户信息，找不到时使用默认值"""
    for member in member_list:
        if member["user_id"] == user_id:
            return member
    
    # 未找到时使用默认信息
    logger.warning(f"用户 {user_id} 不在成员列表中，使用默认信息")
    return {
        "user_id": user_id,
        "nickname": f"用户{user_id}",
        "card": f"用户{user_id}",
        "avatar": "https://q1.qlogo.cn/g?b=qq&nk=1&s=640"
    }

# 配对指令
pair_cmd = on_command(
    "wife",
    priority=5,
    block=True,
    permission=lambda event: isinstance(event, GroupMessageEvent)
)

@pair_cmd.handle()
async def handle_pair(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id
    user_id = event.user_id
    
    # 获取或生成配对
    partner_id = await get_or_generate_pair(bot, group_id, user_id)
    
    if partner_id is None:
        await pair_cmd.finish("今日群内成员已全部配对完毕，或没有足够的可用成员，明天再来吧~")
    
    # 复用成员列表，避免重复调用API
    member_list = await get_valid_group_members(bot, group_id)
    
    # 从成员列表中直接获取信息，不单独调用API
    user_info = get_user_info(member_list, user_id)
    partner_info = get_user_info(member_list, partner_id)
    
    # 构建回复消息
    reply_msg = Message(
        MessageSegment.at(user_id) + "\n"
        f"你今天的群老婆是：【{partner_info['card']}】嘿嘿~！\n"
        f"Ta的QQ号：{partner_info['user_id']}\n"
        f"头像：\n" + MessageSegment.image(partner_info["avatar"]) + "\n"
        "（每日0点自动重置配对）"
    )
    
    await pair_cmd.finish(reply_msg)