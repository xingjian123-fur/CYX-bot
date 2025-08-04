from pathlib import Path

import nonebot
from nonebot import get_plugin_config
from nonebot.plugin import PluginMetadata

from .config import Config

__plugin_meta__ = PluginMetadata(
    name="weijinci",
    description="",
    usage="",
    config=Config,
)

config = get_plugin_config(Config)

sub_plugins = nonebot.load_plugins(
    str(Path(__file__).parent.joinpath("plugins").resolve())
)

from nonebot import on_message, on_command, logger, get_bot, on
from nonebot.adapters.onebot.v11 import (
    MessageEvent, Message, GroupMessageEvent,
    Bot
)
from nonebot.rule import Rule
from nonebot.permission import SUPERUSER
from nonebot.plugin import PluginMetadata
from nonebot.params import CommandArg
from pathlib import Path
import json
from typing import Set, Optional, List
from asyncio import Lock

# 插件元数据
__plugin_meta__ = PluginMetadata(
    name="指令消息违禁词拦截",
    description="仅检查指令调用消息和机器人返回内容的违禁词拦截插件",
    usage="""
    管理员命令：
    - 添加违禁词 [词1] [词2]...
    - 删除违禁词 [词1] [词2]...
    - 查看违禁词
    """,
    extra={"author": "NoneBot2 用户"}
)

# 违禁词存储配置
DATA_PATH = Path(__file__).parent / "data"
DATA_PATH.mkdir(exist_ok=True)
WORDLIST_FILE = DATA_PATH / "wordlist.json"
DEFAULT_WORDS = {"违禁词1", "敏感词1", "违规内容"}  # 初始词库

# 全局变量与锁
banned_words: Set[str] = set()
message_lock = Lock()  # 确保并发安全


# 加载/保存违禁词库
def load_wordlist() -> Set[str]:
    try:
        if WORDLIST_FILE.exists():
            with open(WORDLIST_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        save_wordlist(DEFAULT_WORDS)
        return DEFAULT_WORDS
    except Exception as e:
        logger.error(f"加载违禁词库失败: {e}")
        return DEFAULT_WORDS

def save_wordlist(words: Set[str]) -> None:
    try:
        with open(WORDLIST_FILE, "w", encoding="utf-8") as f:
            json.dump(list(words), f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"保存违禁词库失败: {e}")

# 初始化加载词库
banned_words = load_wordlist()


# 核心检测函数
def check_banned_content(text: str) -> Optional[str]:
    """检测文本是否包含违禁词，返回第一个命中的词"""
    if not text:
        return None
    text_lower = text.lower()
    for word in banned_words:
        if word.lower() in text_lower:
            return word
    return None


# 1. 拦截用户调用指令时的消息
async def is_command_message(event: MessageEvent) -> bool:
    """规则：判断是否为指令调用消息"""
    # 提取消息中的指令前缀（适配默认配置的命令前缀）
    bot = get_bot()
    cmd_prefixes = bot.config.command_start
    message_text = event.get_plaintext().lstrip()
    return any(message_text.startswith(prefix) for prefix in cmd_prefixes)

# 注册指令消息检测器（优先级最高）
command_checker = on_message(
    rule=Rule(is_command_message),
    priority=1,
    block=False
)

@command_checker.handle()
async def handle_command_message(event: MessageEvent):
    """检测用户发送的指令消息"""
    # 正确的超级用户权限检查方式
    if await SUPERUSER(bot=get_bot(), event=event):
        return  # 超级用户消息不拦截
    
    text = event.get_plaintext().strip()
    banned_word = check_banned_content(text)
    if banned_word:
        logger.warning(
            f"指令消息拦截: {banned_word} "
            f"发送者: {event.user_id} "
            f"内容: {text[:50]}..."
        )
        # 根据场景发送提示
        prompt = "指令包含敏感内容，已拦截"
        if isinstance(event, GroupMessageEvent):
            prompt = f"[群聊拦截] {prompt}"
        await command_checker.finish(Message(prompt))


# 2. 拦截机器人的返回内容（修正钩子实现，移除 always_false）
from nonebot.matcher import Matcher

# 自定义一个永远返回 False 的规则（替代 always_false）
async def never_trigger() -> bool:
    return False

# 注册全局后置处理器（使用自定义规则确保不主动触发）
global_post_processor = on(rule=Rule(never_trigger), priority=0, block=False)

@global_post_processor.handle()
async def check_bot_response(matcher: Matcher, bot: Bot, event: MessageEvent):
    """在所有消息回复前检查内容"""
    # 超级用户不受限制
    if await SUPERUSER(bot=bot, event=event):
        return
    
    # 获取即将发送的回复内容（兼容不同版本的 Matcher 结构）
    if hasattr(matcher, "_message"):
        message = matcher._message
    elif "message" in matcher.state:
        message = matcher.state["message"]
    else:
        return  # 无回复内容则跳过
    
    # 提取文本内容
    text_segments: List[str] = []
    for seg in message:
        if seg.type == "text":
            text_segments.append(str(seg))
    full_text = "".join(text_segments)
    
    # 检测违禁词
    banned_word = check_banned_content(full_text)
    if banned_word:
        logger.warning(
            f"机器人回复拦截: {banned_word} "
            f"接收者: {event.user_id} "
            f"内容: {full_text[:50]}..."
        )
        # 替换为安全内容
        if hasattr(matcher, "_message"):
            matcher._message = Message("回复内容包含敏感信息，已屏蔽")
        elif "message" in matcher.state:
            matcher.state["message"] = Message("回复内容包含敏感信息，已屏蔽")


# 3. 管理员管理命令
# 添加违禁词
add_cmd = on_command("添加违禁词", permission=SUPERUSER, priority=5, block=True)
@add_cmd.handle()
async def handle_add(args: Message = CommandArg()):
    words = args.extract_plain_text().strip().split()
    if not words:
        await add_cmd.finish("请输入要添加的违禁词，例如：添加违禁词 词1 词2")
    
    async with message_lock:
        added = 0
        for word in words:
            if word not in banned_words:
                banned_words.add(word)
                added += 1
        save_wordlist(banned_words)
    await add_cmd.finish(f"成功添加 {added} 个违禁词，当前共 {len(banned_words)} 个")

# 删除违禁词
del_cmd = on_command("删除违禁词", permission=SUPERUSER, priority=5, block=True)
@del_cmd.handle()
async def handle_del(args: Message = CommandArg()):
    words = args.extract_plain_text().strip().split()
    if not words:
        await del_cmd.finish("请输入要删除的违禁词，例如：删除违禁词 词1 词2")
    
    async with message_lock:
        deleted = 0
        for word in words:
            if word in banned_words:
                banned_words.remove(word)
                deleted += 1
        save_wordlist(banned_words)
    await del_cmd.finish(f"成功删除 {deleted} 个违禁词，当前共 {len(banned_words)} 个")

# 查看违禁词
show_cmd = on_command("查看违禁词", permission=SUPERUSER, priority=5, block=True)
@show_cmd.handle()
async def handle_show():
    if not banned_words:
        await show_cmd.finish("当前无违禁词")
    
    word_list = list(banned_words)
    msg = "当前违禁词列表：\n" + "、".join(word_list)
    await show_cmd.finish(msg)