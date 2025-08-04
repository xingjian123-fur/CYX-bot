from pathlib import Path

import nonebot
from nonebot import get_plugin_config
from nonebot.plugin import PluginMetadata

from .config import Config

__plugin_meta__ = PluginMetadata(
    name="dinshiwenho",
    description="",
    usage="",
    config=Config,
)

config = get_plugin_config(Config)

sub_plugins = nonebot.load_plugins(
    str(Path(__file__).parent.joinpath("plugins").resolve())
)

from nonebot import require, on_notice, logger, get_driver
from nonebot.adapters.onebot.v11 import Bot, GroupIncreaseNoticeEvent
from nonebot_plugin_apscheduler import scheduler
import json
import os
import random
import asyncio
from datetime import datetime
from pathlib import Path

# 群聊缓存文件路径
GROUP_CACHE_PATH = Path(__file__).parent / "group_cache.json"

# 初始化群聊缓存
class GroupCache:
    def __init__(self):
        self.groups = []
        self.load_cache()

    def load_cache(self):
        """从文件加载群聊缓存"""
        if os.path.exists(GROUP_CACHE_PATH):
            try:
                with open(GROUP_CACHE_PATH, "r", encoding="utf-8") as f:
                    self.groups = json.load(f)
                logger.info(f"已加载 {len(self.groups)} 个群聊缓存")
            except Exception as e:
                logger.error(f"加载群聊缓存失败: {e}")
                self.groups = []

    def save_cache(self):
        """保存群聊缓存到文件"""
        try:
            with open(GROUP_CACHE_PATH, "w", encoding="utf-8") as f:
                json.dump(self.groups, f, ensure_ascii=False, indent=2)
            logger.info(f"已保存 {len(self.groups)} 个群聊缓存")
        except Exception as e:
            logger.error(f"保存群聊缓存失败: {e}")

    def add_group(self, group_id: int, group_name: str = ""):
        """添加群聊到缓存（去重）"""
        if not any(g["group_id"] == group_id for g in self.groups):
            self.groups.append({
                "group_id": group_id,
                "group_name": group_name,
                "added_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            self.save_cache()
            logger.info(f"新增群聊缓存: {group_id} {group_name}")

    def get_all_groups(self) -> list[int]:
        """获取所有群聊ID"""
        return [g["group_id"] for g in self.groups]

# 初始化群聊缓存
group_cache = GroupCache()

# 读取名言警句
def load_quotes():
    try:
        with open("quotes.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("quotes", [])
    except FileNotFoundError:
        logger.warning("未找到quotes.json文件，使用默认名言")
        return ["今日事，今日毕 —— 佚名"]

quotes_list = load_quotes()

# 随机获取一条名言
def get_random_quote():
    return random.choice(quotes_list) if quotes_list else "愿你今日安好"

# 初始化群聊缓存（延迟执行，确保bot已就绪）
async def init_group_cache(bot: Bot):
    try:
        # 获取群列表（OneBot协议）
        groups = await bot.get_group_list()
        for group in groups:
            group_cache.add_group(group["group_id"], group.get("group_name", ""))
        logger.info("群聊缓存初始化完成")
    except Exception as e:
        logger.error(f"初始化群聊缓存失败: {e}")

# 监听bot就绪事件（关键修复：在bot连接成功后执行初始化）
driver = get_driver()
@driver.on_bot_connect
async def handle_bot_connect(bot: Bot):
    """当bot成功连接后，初始化群聊缓存"""
    logger.info("机器人已连接，开始初始化群聊缓存...")
    await init_group_cache(bot)  # 传入已就绪的bot实例

# 监听加入新群聊事件
@on_notice().handle()
async def handle_join_group(bot: Bot, event: GroupIncreaseNoticeEvent):
    # 检查是否是机器人自己加入群聊
    if event.user_id == bot.self_id:
        group_id = event.group_id
        # 尝试获取群名称
        try:
            group_info = await bot.get_group_info(group_id=group_id)
            group_name = group_info.get("group_name", "")
        except:
            group_name = ""
        group_cache.add_group(group_id, group_name)
        logger.info(f"机器人加入新群聊，已缓存: {group_id} {group_name}")

# 发送问候消息到所有群聊
async def send_greeting_to_all_groups():
    groups = group_cache.get_all_groups()
    if not groups:
        logger.warning("没有缓存的群聊，不发送消息")
        return

    current_hour = datetime.now().hour
    # 根据时段生成问候语
    if 6 <= current_hour < 12:
        greeting = ("早上好呀，群里的小伙伴们！新的一天开始了，一起加油～ \n 看看星电的吹水群吗~ 730558913 \n 舞萌功能感谢大佬开源！"
       )
    elif 12 <= current_hour < 14:
        greeting = ("中午好！大家记得按时吃饭，补充能量哦～\n 看看星电的吹水群吗~ 730558913 \n 舞萌功能感谢大佬开源！"
        )
    elif 18 <= current_hour < 22:
        greeting = ("晚上好呀，忙碌了一天，好好放松一下吧～\n 看看星电的吹水群吗~ 730558913 \n 舞萌功能感谢大佬开源！"
        )
    else:
        greeting = ("凌晨好，还没休息的小伙伴注意身体，早点休息哦～ \n 看看星电的吹水群吗~ 730558913 \n 舞萌功能感谢大佬开源！"
        )
    
    quote = get_random_quote()
    message = f"{greeting}\n今日名言：{quote}"

    # 获取当前已连接的bot
    try:
        bot = get_driver().bots.values().__iter__().__next__()  # 获取第一个可用bot
    except StopIteration:
        logger.error("没有可用的机器人，无法发送消息")
        return

    # 发送消息到每个群聊
    for group_id in groups:
        try:
            await bot.send_group_msg(group_id=group_id, message=message)
            logger.info(f"已向群 {group_id} 发送问候消息")
            await asyncio.sleep(1)  # 避免发送过快被限制
        except Exception as e:
            logger.error(f"向群 {group_id} 发送消息失败: {e}")

# 定时任务设置
require("nonebot_plugin_apscheduler")
from nonebot_plugin_apscheduler import scheduler

# 每天定时发送问候
scheduler.add_job(
    send_greeting_to_all_groups,
    "cron",
    hour="8",
    id="morning_greeting"
)
scheduler.add_job(
    send_greeting_to_all_groups,
    "cron",
    hour="12",
    id="noon_greeting"
)
scheduler.add_job(
    send_greeting_to_all_groups,
    "cron",
    hour="20",
    id="evening_greeting"
)
scheduler.add_job(
    send_greeting_to_all_groups,
    "cron",
    hour="0",
    id="midnight_greeting"
)