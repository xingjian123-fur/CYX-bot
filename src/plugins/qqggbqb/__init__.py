from pathlib import Path

import nonebot
from nonebot import get_plugin_config
from nonebot.plugin import PluginMetadata

from .config import Config

__plugin_meta__ = PluginMetadata(
    name="qqggbqb",
    description="",
    usage="",
    config=Config,
)

config = get_plugin_config(Config)

sub_plugins = nonebot.load_plugins(
    str(Path(__file__).parent.joinpath("plugins").resolve())
)

import os
import base64
import random
from datetime import datetime, timedelta, time
from pathlib import Path
from io import BytesIO
from PIL import Image
from nonebot import get_driver, logger, on_command, get_bots
from nonebot.adapters import Message
from nonebot.params import CommandArg
from nonebot.plugin import PluginMetadata, require
from nonebot.rule import to_me

# 依赖定时任务插件
require("nonebot_plugin_apscheduler")
from nonebot_plugin_apscheduler import scheduler

# 插件元数据
__plugin_meta__ = PluginMetadata(
    name="定时群聊差异图片发送",
    description="每天随机时间点向不同群聊发送不同图片（自动降低分辨率）",
    usage="""
    配置图片文件夹、目标宽度和目标群聊列表
    插件每天随机生成8个时间点，每个群聊会收到不同图片
    """,
    type="application",
    config=None
)

# 配置项
class Config:
    image_folder: Path = Path("images")  # 图片文件夹路径
    resized_width: int = 800             # 调整后的图片宽度
    target_groups: list[int] = []        # 目标群聊列表（为空则发送到所有群聊）

# 加载配置
config = Config()
driver = get_driver()
if hasattr(driver.config, "image_folder"):
    config.image_folder = Path(driver.config.image_folder)
if hasattr(driver.config, "resized_width"):
    config.resized_width = driver.config.resized_width
if hasattr(driver.config, "target_groups"):
    config.target_groups = driver.config.target_groups

# 确保图片文件夹存在
if not config.image_folder.exists():
    config.image_folder.mkdir(parents=True, exist_ok=True)
    logger.warning(f"图片文件夹不存在，已自动创建：{config.image_folder}")

# 存储当天的定时任务ID
daily_jobs = []

async def send_image_task():
    """发送图片任务（为每个群聊单独选择不同图片）"""
    # 获取所有可用机器人
    bots = get_bots()
    if not bots:
        logger.warning("没有可用的机器人，跳过发送任务")
        return

    for bot_id, bot in bots.items():
        try:
            # 适配OneBot V11适配器
            if "onebot" not in bot.adapter.get_name().lower():
                continue

            # 获取目标群聊列表
            if config.target_groups:
                groups = [{"group_id": gid} for gid in config.target_groups]
            else:
                groups = await bot.call_api("get_group_list")

            # 为每个群聊单独选择并发送图片
            for group in groups:
                group_id = group.get("group_id")
                if not group_id:
                    continue

                # 【核心修改】为当前群聊单独随机选择一张图片
                image_info = get_random_image(str(config.image_folder))
                if not image_info:
                    logger.warning(f"群聊 {group_id} 无可用图片，跳过发送")
                    continue
                image, filename = image_info

                # 处理图片（调整分辨率+转换格式）
                resized_img = resize_image(image, config.resized_width)
                img_bytes = image_to_bytes(resized_img, os.path.splitext(filename)[1].lower())
                base64_str = base64.b64encode(img_bytes.getvalue()).decode("utf-8")

                # 发送到当前群聊
                await bot.call_api(
                    "send_group_msg",
                    group_id=group_id,
                    message=[
                        
                        {"type": "image", "data": {"file": f"base64://{base64_str}"}}
                    ]
                )
                logger.info(f"已向群聊 {group_id} 发送图片：{filename}")

        except Exception as e:
            logger.error(f"机器人 {bot_id} 发送任务失败：{str(e)}")

def get_random_image(folder_path: str) -> tuple[Image.Image, str] | None:
    """从文件夹随机获取一张图片并转换为兼容模式"""
    if not os.path.isdir(folder_path):
        logger.error(f"图片文件夹不存在：{folder_path}")
        return None

    # 筛选支持的图片格式
    supported_ext = ('.jpg', '.jpeg', '.png', '.gif', '.bmp')
    image_files = [
        os.path.join(folder_path, f)
        for f in os.listdir(folder_path)
        if os.path.isfile(os.path.join(folder_path, f)) and f.lower().endswith(supported_ext)
    ]

    if not image_files:
        logger.warning(f"图片文件夹为空或无支持的图片格式：{folder_path}")
        return None

    # 随机选择一张图片并转换模式
    try:
        selected_path = random.choice(image_files)
        with Image.open(selected_path) as img:
            return convert_image_mode(img), os.path.basename(selected_path)
    except Exception as e:
        logger.error(f"处理图片 {selected_path} 失败：{str(e)}")
        return None

def convert_image_mode(image: Image.Image) -> Image.Image:
    """转换图片模式以支持正确保存（处理调色板/透明通道）"""
    if image.mode == 'P':
        return image.convert('RGBA') if 'transparency' in image.info else image.convert('RGB')
    elif image.mode in ('RGBA', 'LA'):
        return image
    return image.convert('RGB')

def resize_image(image: Image.Image, target_width: int) -> Image.Image:
    """按目标宽度等比例调整图片大小"""
    if image.width <= target_width:
        return image
    ratio = target_width / image.width
    return image.resize(
        (target_width, int(image.height * ratio)),
        Image.LANCZOS  # 高质量缩放算法
    )

def image_to_bytes(image: Image.Image, ext: str) -> BytesIO:
    """将图片转换为字节流（根据格式自动选择保存方式）"""
    buf = BytesIO()
    if ext in ('.png', '.gif') or image.mode in ('RGBA', 'LA'):
        image.save(buf, format='PNG', optimize=True)
    else:
        if image.mode in ('RGBA', 'LA'):
            # 为透明图片添加白色背景
            bg = Image.new('RGB', image.size, (255, 255, 255))
            bg.paste(image, mask=image.split()[-1])
            image = bg
        image.save(buf, format='JPEG', quality=85, optimize=True)
    buf.seek(0)
    return buf

def schedule_daily_tasks():
    """每天生成8个随机时间点并安排任务"""
    global daily_jobs
    # 清除历史任务
    for job_id in daily_jobs:
        scheduler.remove_job(job_id)
    daily_jobs.clear()

    # 生成8个随机时间（当天）
    times = sorted([
        time(random.randint(0, 23), random.randint(0, 59), random.randint(0, 59))
        for _ in range(4)
    ])
    logger.info(f"今日发送时间点：{[t.strftime('%H:%M:%S') for t in times]}")

    # 为每个时间点创建任务
    for t in times:
        now = datetime.now()
        run_time = datetime(now.year, now.month, now.day, t.hour, t.minute, t.second)
        if run_time < now:
            run_time += timedelta(days=1)  # 若时间已过则顺延至明天

        job = scheduler.add_job(
            send_image_task,
            "date",
            run_date=run_time,
            id=f"img_send_{run_time.strftime('%Y%m%d_%H%M%S')}"
        )
        daily_jobs.append(job.id)

# 每天凌晨0点更新任务
@scheduler.scheduled_job("cron", hour=0, minute=0)
def reschedule_daily():
    logger.info("更新当天图片发送任务")
    schedule_daily_tasks()

# 初始化时立即安排任务（延迟10秒执行，确保机器人启动完成）
@scheduler.scheduled_job("date", run_date=datetime.now() + timedelta(seconds=10))
def init_tasks():
    logger.info("初始化图片发送任务")
    schedule_daily_tasks()

# 手动触发命令（方便测试）
send_cmd = on_command("发送差异图片", rule=to_me(), priority=10, block=True)
@send_cmd.handle()
async def handle_manual_send(args: Message = CommandArg()):
    await send_image_task()
    await send_cmd.finish("已向所有目标群聊发送差异图片")