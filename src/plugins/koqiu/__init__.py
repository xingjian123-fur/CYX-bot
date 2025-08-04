from pathlib import Path##豆包咋一堆语法错误

import nonebot
from nonebot import get_plugin_config
from nonebot.plugin import PluginMetadata

from .config import Config


__plugin_meta__ = PluginMetadata(
    name="koqiu",
    description="",
    usage="",
    config=Config,
)

config = get_plugin_config(Config)

sub_plugins = nonebot.load_plugins(
    str(Path(__file__).parent.joinpath("plugins").resolve())
)

import random
from nonebot import on_message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, ActionFailed
from nonebot.exception import FinishedException  # 正确的导入路径
from nonebot.adapters.onebot.v11.permission import GROUP
from nonebot.rule import regex
from nonebot.log import logger

ballgag_matcher = on_message(
    rule=regex(r"^(我要口球|口球我|来个口球|/口球)$"),
    permission=GROUP,
    priority=10,
    block=True
)

MUTE_TIME_OPTIONS = [60, 300, 600, 1800, 3600]
MUTE_TIME_HUMAN_READABLE = ["1分钟", "5分钟", "10分钟", "30分钟", "1小时"]

@ballgag_matcher.handle()
async def handle_ballgag(bot: Bot, event: GroupMessageEvent):
    user_id = event.user_id
    bot_id = event.self_id

    # 防止误禁自己
    if user_id == bot_id:
        await ballgag_matcher.finish("不能对自己执行禁言哦~")

    # 检查机器人权限
    try:
        bot_info = await bot.get_group_member_info(group_id=event.group_id, user_id=bot_id)
    except ActionFailed as e:
        logger.error(f"获取机器人权限失败: {e}")
        await ballgag_matcher.finish("无法确认我的权限，请确保我是群管理员~，拿着截屏去扇星见吧")

    if bot_info["role"] not in ["admin", "owner"]:
        await ballgag_matcher.finish("我需要成为群管理员才能执行禁言哦~记得扇一下群主~")

    # 执行禁言
    try:
        mute_time = random.choice(MUTE_TIME_OPTIONS)
        index = MUTE_TIME_OPTIONS.index(mute_time)
        human_readable_time = MUTE_TIME_HUMAN_READABLE[index]

        # 执行禁言
        await bot.set_group_ban(
            group_id=event.group_id,
            user_id=user_id,
            duration=mute_time
        )

        # 禁言成功后，发送消息并终止处理（只调用一次finish）
        await ballgag_matcher.finish(
            f"{event.sender.card or event.sender.nickname}触发口球惩罚！禁言{human_readable_time}注：管理无法被口球"
        )

    except ActionFailed as e:
        # 处理禁言失败（如禁言管理员）
        if "管理员" in str(e) or "权限" in str(e):
            await ballgag_matcher.finish("管理员不能被禁言哦~")
        else:
            logger.error(f"禁言失败: {e}")
            await ballgag_matcher.finish("禁言失败，请稍后再试~")

    except FinishedException:
        # 捕获重复finish导致的异常，不做额外处理
        pass

    except Exception as e:
        logger.error(f"其他错误: {e}")
        await ballgag_matcher.finish("操作异常，请稍后再试~，拿着截屏去扇星见吧")