
import asyncio
import json
import os
import pytz
from datetime import datetime, time, timedelta
from nonebot import on_command, on_startswith
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, MessageSegment
from nonebot.plugin import PluginMetadata
from nonebot.log import logger
from nonebot.rule import to_me
from nonebot.permission import SUPERUSER

# 配置文件路径
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "groups_config.json")

# 确保配置文件存在
if not os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump({"groups": {}}, f, ensure_ascii=False, indent=2)

# 加载配置
def load_config():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"加载配置文件失败: {e}")
        return {"groups": {}}

# 保存配置
def save_config(config):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"保存配置文件失败: {e}")

# 获取群配置，如果不存在则返回默认配置
def get_group_config(group_id):
    config = load_config()
    groups = config.get("groups", {})
    return groups.get(str(group_id), {
        "enabled": False,
        "timezone": "Asia/Shanghai",
        "start_time": {"hour": 22, "minute": 0},
        "end_time": {"hour": 7, "minute": 0},
        "mute_message": "现在是禁言时间，请勿发言！",
        "unmute_message": "禁言时间已结束，大家可以畅所欲言！",
        "mute_image_path": "mute.png",
        "unmute_image_path": "unmute.png"
    })

# 更新群配置
def update_group_config(group_id, new_config):
    config = load_config()
    groups = config.setdefault("groups", {})
    groups[str(group_id)] = new_config
    save_config(config)

# 检查当前是否处于禁言时间段
def is_mute_time(group_config):
    tz = pytz.timezone(group_config.get("timezone", "Asia/Shanghai"))
    now = datetime.now(tz).time()
    start_time = time(**group_config["start_time"])
    end_time = time(**group_config["end_time"])
    
    # 如果开始时间晚于结束时间（跨越午夜）
    if start_time > end_time:
        return now >= start_time or now < end_time
    # 开始时间早于结束时间（同一天内）
    return start_time <= now < end_time

# 计算下次检查时间
def get_next_check_time() -> int:
    now = datetime.now()
    next_minute = (now + timedelta(minutes=1)).replace(second=0, microsecond=0)
    return int((next_minute - now).total_seconds())

# 对指定群执行禁言/解除禁言操作
async def process_group(bot: Bot, group_id: int):
    group_config = get_group_config(group_id)
    if not group_config["enabled"]:
        return
    
    try:
        if is_mute_time(group_config):
            # 禁言操作
            await bot.set_group_whole_ban(group_id=group_id, enable=True)
            # 发送禁言通知
            message = group_config["mute_message"]
            image_path = group_config["mute_image_path"]
            if image_path and os.path.exists(image_path):
                message += MessageSegment.image(f"file:///{os.path.abspath(image_path)}")
            await bot.send_group_msg(group_id=group_id, message=message)
            logger.info(f"对群 {group_id} 执行禁言")
        else:
            # 解除禁言操作
            await bot.set_group_whole_ban(group_id=group_id, enable=False)
            # 发送解禁通知
            message = group_config["unmute_message"]
            image_path = group_config["unmute_image_path"]
            if image_path and os.path.exists(image_path):
                message += MessageSegment.image(f"file:///{os.path.abspath(image_path)}")
            await bot.send_group_msg(group_id=group_id, message=message)
            logger.info(f"对群 {group_id} 解除禁言")
    except Exception as e:
        logger.error(f"处理群 {group_id} 时出错: {e}")

# 定时任务，每分钟检查一次
async def scheduled_task(bot: Bot):
    while True:
        try:
            config = load_config()
            for group_id_str in config.get("groups", {}):
                group_id = int(group_id_str)
                await process_group(bot, group_id)
        except Exception as e:
            logger.error(f"定时任务执行出错: {e}")
        await asyncio.sleep(get_next_check_time())

# 机器人启动时注册定时任务
from nonebot import get_bots
async def startup():
    bots = get_bots()
    if bots:
        bot = list(bots.values())[0]
        asyncio.create_task(scheduled_task(bot))
    else:
        logger.warning("没有可用的Bot连接，定时任务无法启动")

# 注册启动钩子
from nonebot import on_bot_connect
nonebot.on_startup(startup)

# 命令处理 - 开启禁言（群管理员/群主可用）
enable_cmd = on_command("开启禁言", rule=to_me(), priority=5)
@enable_cmd.handle()
async def handle_enable(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id
    group_config = get_group_config(group_id)
    
    # 检查用户权限
    sender = event.sender
    if sender.role not in ["admin", "owner"] and not await SUPERUSER(bot, event):
        await enable_cmd.finish("你没有权限执行此操作！")
    
    if group_config["enabled"]:
        await enable_cmd.finish("本群已经开启自动禁言功能")
    
    group_config["enabled"] = True
    update_group_config(group_id, group_config)
    await enable_cmd.finish("已开启本群自动禁言功能")

# 命令处理 - 关闭禁言（群管理员/群主可用）
disable_cmd = on_command("关闭禁言", rule=to_me(), priority=5)
@disable_cmd.handle()
async def handle_disable(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id
    group_config = get_group_config(group_id)
    
    # 检查用户权限
    sender = event.sender
    if sender.role not in ["admin", "owner"] and not await SUPERUSER(bot, event):
        await disable_cmd.finish("你没有权限执行此操作！")
    
    if not group_config["enabled"]:
        await disable_cmd.finish("本群未开启自动禁言功能")
    
    group_config["enabled"] = False
    update_group_config(group_id, group_config)
    
    # 如果当前处于禁言时段，关闭时立即解除禁言
    if is_mute_time(group_config):
        try:
            await bot.set_group_whole_ban(group_id=group_id, enable=False)
        except Exception as e:
            logger.error(f"关闭禁言时解除禁言失败: {e}")
    
    await disable_cmd.finish("已关闭本群自动禁言功能")

# 命令处理 - 查看禁言状态
status_cmd = on_command("禁言状态", rule=to_me(), priority=5)
@status_cmd.handle()
async def handle_status(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id
    group_config = get_group_config(group_id)
    
    status = "已开启" if group_config["enabled"] else "已关闭"
    time_status = "当前处于禁言时段" if is_mute_time(group_config) else "当前不处于禁言时段"
    
    start_time = f"{group_config['start_time']['hour']:02d}:{group_config['start_time']['minute']:02d}"
    end_time = f"{group_config['end_time']['hour']:02d}:{group_config['end_time']['minute']:02d}"
    
    await status_cmd.finish(f"本群自动禁言状态: {status}\n禁言时间段: {start_time} - {end_time}\n{time_status}")

# 命令处理 - 查看配置（超级用户可用）
view_config_cmd = on_command("查看配置", rule=to_me(), permission=SUPERUSER, priority=5)
@view_config_cmd.handle()
async def handle_view_config(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id
    group_config = get_group_config(group_id)
    
    config_text = json.dumps(group_config, ensure_ascii=False, indent=2)
    await view_config_cmd.finish(f"本群配置信息:\n```json\n{config_text}\n```")

# 命令处理 - 设置禁言时间（群管理员/群主可用）
set_time_cmd = on_command("设置禁言时间", rule=to_me(), priority=5)
@set_time_cmd.handle()
async def handle_set_time(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id
    args = event.get_plaintext().strip().split()
    
    # 检查用户权限
    sender = event.sender
    if sender.role not in ["admin", "owner"] and not await SUPERUSER(bot, event):
        await set_time_cmd.finish("你没有权限执行此操作！")
    
    if len(args) != 3:
        await set_time_cmd.finish("使用方法: 设置禁言时间 开始小时:开始分钟 结束小时:结束分钟\n示例: 设置禁言时间 22:00 07:00")
    
    try:
        start_str, end_str = args[1], args[2]
        start_hour, start_minute = map(int, start_str.split(":"))
        end_hour, end_minute = map(int, end_str.split(":"))
        
        # 验证时间格式
        if not (0 <= start_hour <= 23 and 0 <= start_minute <= 59 and 0 <= end_hour <= 23 and 0 <= end_minute <= 59):
            await set_time_cmd.finish("时间格式错误，请使用 HH:MM 格式")
        
        group_config = get_group_config(group_id)
        group_config["start_time"] = {"hour": start_hour, "minute": start_minute}
        group_config["end_time"] = {"hour": end_hour, "minute": end_minute}
        update_group_config(group_id, group_config)
        
        await set_time_cmd.finish(f"已更新禁言时间段为: {start_str} - {end_str}")
    except Exception as e:
        await set_time_cmd.finish(f"设置失败: {str(e)}")

# 命令处理 - 设置禁言消息（群管理员/群主可用）
set_mute_msg_cmd = on_command("设置禁言消息", rule=to_me(), priority=5)
@set_mute_msg_cmd.handle()
async def handle_set_mute_msg(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id
    new_message = event.get_plaintext().strip()[6:].strip()
    
    # 检查用户权限
    sender = event.sender
    if sender.role not in ["admin", "owner"] and not await SUPERUSER(bot, event):
        await set_mute_msg_cmd.finish("你没有权限执行此操作！")
    
    if not new_message:
        await set_mute_msg_cmd.finish("禁言消息不能为空")
    
    group_config = get_group_config(group_id)
    group_config["mute_message"] = new_message
    update_group_config(group_id, group_config)
    
    await set_mute_msg_cmd.finish("已更新禁言消息")

# 命令处理 - 设置解禁消息（群管理员/群主可用）
set_unmute_msg_cmd = on_command("设置解禁消息", rule=to_me(), priority=5)
@set_unmute_msg_cmd.handle()
async def handle_set_unmute_msg(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id
    new_message = event.get_plaintext().strip()[6:].strip()
    
    # 检查用户权限
    sender = event.sender
    if sender.role not in ["admin", "owner"] and not await SUPERUSER(bot, event):
        await set_unmute_msg_cmd.finish("你没有权限执行此操作！")
    
    if not new_message:
        await set_unmute_msg_cmd.finish("解禁消息不能为空")
    
    group_config = get_group_config(group_id)
    group_config["unmute_message"] = new_message
    update_group_config(group_id, group_config)
    
    await set_unmute_msg_cmd.finish("已更新解禁消息")

# 命令处理 - 设置禁言图片路径（群管理员/群主可用）
set_mute_img_cmd = on_command("设置禁言图片", rule=to_me(), priority=5)
@set_mute_img_cmd.handle()
async def handle_set_mute_img(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id
    new_path = event.get_plaintext().strip()[6:].strip()
    
    # 检查用户权限
    sender = event.sender
    if sender.role not in ["admin", "owner"] and not await SUPERUSER(bot, event):
        await set_mute_img_cmd.finish("你没有权限执行此操作！")
    
    if not new_path:
        await set_mute_img_cmd.finish("图片路径不能为空")
    
    # 检查图片是否存在
    if not os.path.exists(new_path) and not os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), new_path)):
        await set_mute_img_cmd.finish("图片不存在，请检查路径是否正确")
    
    group_config = get_group_config(group_id)
    group_config["mute_image_path"] = new_path
    update_group_config(group_id, group_config)
    
    await set_mute_img_cmd.finish("已更新禁言图片路径")

# 命令处理 - 设置解禁图片路径（群管理员/群主可用）
set_unmute_img_cmd = on_command("设置解禁图片", rule=to_me(), priority=5)
@set_unmute_img_cmd.handle()
async def handle_set_unmute_img(bot: Bot, event: GroupMessageEvent):
    group_id = event.group_id
    new_path = event.get_plaintext().strip()[6:].strip()
    
    # 检查用户权限
    sender = event.sender
    if sender.role not in ["admin", "owner"] and not await SUPERUSER(bot, event):
        await set_unmute_img_cmd.finish("你没有权限执行此操作！")
    
    if not new_path:
        await set_unmute_img_cmd.finish("图片路径不能为空")
    
    # 检查图片是否存在
    if not os.path.exists(new_path) and not os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), new_path)):
        await set_unmute_img_cmd.finish("图片不存在，请检查路径是否正确")
    
    group_config = get_group_config(group_id)
    group_config["unmute_image_path"] = new_path
    update_group_config(group_id, group_config)
    
    await set_unmute_img_cmd.finish("已更新解禁图片路径")

# 命令处理 - 重载配置（超级用户可用）
reload_cmd = on_command("重载配置", rule=to_me(), permission=SUPERUSER, priority=5)
@reload_cmd.handle()
async def handle_reload(bot: Bot, event: GroupMessageEvent):
    # 重新加载配置
    load_config()
    await reload_cmd.finish("配置已重新加载")

# 命令处理 - 使用帮助
help_cmd = on_command("禁言帮助", rule=to_me(), priority=5)
@help_cmd.handle()
async def handle_help(bot: Bot, event: GroupMessageEvent):
    help_text = """
自动禁言插件使用帮助：

管理员/群主可用命令：
- 开启禁言 - 启用本群自动禁言功能
- 关闭禁言 - 停用本群自动禁言功能
- 禁言状态 - 查看当前禁言状态和设置
- 设置禁言时间 开始时间 结束时间 - 设置禁言时间段（格式：HH:MM）
- 设置禁言消息 内容 - 设置禁言时发送的消息
- 设置解禁消息 内容 - 设置解禁时发送的消息
- 设置禁言图片 路径 - 设置禁言时发送的图片
- 设置解禁图片 路径 - 设置解禁时发送的图片

超级用户可用命令：
- 查看配置 - 查看本群详细配置信息
- 重载配置 - 重新加载配置文件

使用示例：
- 设置禁言时间 22:00 07:00
- 设置禁言消息 现在是休息时间，请保持安静！
- 设置禁言图片 mute.png
    """
    await help_cmd.finish(help_text.strip())

__plugin_meta__ = PluginMetadata(
    name="自动禁言",
    description="每晚自动开启群禁言，早上自动解除，支持多群独立配置",
    usage=help_text.strip(),
    extra={"author": "yourname", "version": "1.0.0"},
)   