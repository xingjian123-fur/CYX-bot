from pathlib import Path

import nonebot
from nonebot import get_plugin_config
from nonebot.plugin import PluginMetadata

from .config import Config

__plugin_meta__ = PluginMetadata(
    name="wumengping",
    description="",
    usage="",
    config=Config,
)

config = get_plugin_config(Config)

sub_plugins = nonebot.load_plugins(
    str(Path(__file__).parent.joinpath("plugins").resolve())
)

import os
import json
import time
import asyncio
import platform
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional

import matplotlib.pyplot as plt
import numpy as np
from ping3 import ping

from nonebot import on_command, get_driver, logger, require
from nonebot.adapters.onebot.v11 import (
    Bot,
    GroupMessageEvent,
    PrivateMessageEvent,
    MessageSegment,
    Message,
    Event
)
from nonebot.permission import SUPERUSER
from nonebot.plugin import PluginMetadata

# 引入调度器插件
scheduler = require("nonebot_plugin_apscheduler").scheduler

# 插件元信息
__plugin_meta__ = PluginMetadata(
    name="舞萌服务器监控",
    description="每分钟Ping舞萌相关服务器，生成带正常百分比的状态图表",
    usage="发送 '监控图表' 查看状态，管理员发送 '设置监控地址 地址1,2,3,4' 自定义地址"
)

# 配置与常量
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
PING_DATA_FILE = DATA_DIR / "ping_data.json"  # 存储监控数据
CONFIG_FILE = DATA_DIR / "config.json"       # 存储监控地址配置
# 预设监控地址
PRESET_ADDRESSES = [
    "wechat.aime.wumeng.com",  # 舞萌微信AIME服务器
    "qr.aime.wumeng.com",      # 玩家二维码服务器
    "game.aime.wumeng.com",    # 舞萌游戏服务器
    "www.hualixy.com"          # 华立官网
]
CHECK_INTERVAL = 60  # 检测间隔（秒）
MAX_DAY_DATA = 1440  # 一天的分钟数（24*60）

# 确保中文显示正常
plt.rcParams["font.family"] = ["SimHei", "WenQuanYi Micro Hei", "Heiti TC"]
plt.rcParams["axes.unicode_minus"] = False  # 解决负号显示问题

# 数据结构定义
PingRecord = Dict[str, List[Tuple[int, float]]]  # {地址: [(时间戳, 延迟ms)]}
AddressConfig = List[str]  # 监控地址列表


# 工具函数：数据存储与加载
def load_ping_data() -> PingRecord:
    """加载历史Ping数据"""
    if PING_DATA_FILE.exists():
        try:
            with open(PING_DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载Ping数据失败: {e}")
    return {}


def save_ping_data(data: PingRecord):
    """保存Ping数据"""
    try:
        with open(PING_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"保存Ping数据失败: {e}")


def load_address_config() -> AddressConfig:
    """加载监控地址配置，无配置则使用预设地址"""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载地址配置失败，使用预设地址: {e}")
    
    # 首次启动自动创建配置文件
    save_address_config(PRESET_ADDRESSES)
    return PRESET_ADDRESSES


def save_address_config(addresses: AddressConfig):
    """保存监控地址配置（限制4个地址）"""
    if len(addresses) != 4:
        raise ValueError("必须设置4个地址")
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(addresses, f, ensure_ascii=False, indent=2)
        logger.info(f"已更新监控地址: {addresses}")
    except Exception as e:
        logger.error(f"保存地址配置失败: {e}")


# 核心功能：Ping检测与数据清理
async def ping_address(address: str) -> Optional[float]:
    """Ping指定地址，返回延迟（ms），失败返回None"""
    try:
        timeout = 3  # 超时时间（秒）
        if platform.system().lower() == "windows":
            response = ping(address, timeout=timeout, unit="ms")
        else:
            response = ping(address, timeout=timeout) * 1000  # 转换为ms
        return round(response, 2) if response else None
    except Exception as e:
        logger.warning(f"Ping {address} 失败: {e}")
        return None


async def clean_expired_data():
    """清理超过一天的历史数据"""
    ping_data = load_ping_data()
    now = time.time()
    one_day_ago = now - 86400  # 24小时前的时间戳

    # 保留最近一天的数据
    for addr in ping_data:
        ping_data[addr] = [
            (ts, delay) for ts, delay in ping_data[addr]
            if ts >= one_day_ago
        ]

    save_ping_data(ping_data)


async def scheduled_ping():
    """执行一次Ping检测（由调度器控制每分钟执行）"""
    try:
        await clean_expired_data()  # 先清理过期数据

        addresses = load_address_config()
        ping_data = load_ping_data()
        current_ts = int(time.time())

        # 逐个检测地址
        for addr in addresses:
            delay = await ping_address(addr)
            if addr not in ping_data:
                ping_data[addr] = []
            # 限制数据量，超过一天则移除最早数据
            if len(ping_data[addr]) >= MAX_DAY_DATA:
                ping_data[addr].pop(0)
            # 记录结果（异常时延迟为-1）
            ping_data[addr].append((current_ts, delay if delay is not None else -1))

        save_ping_data(ping_data)
        logger.debug(f"完成一次检测: {addresses}")

    except Exception as e:
        logger.error(f"检测出错: {e}")


# 配置定时任务（每分钟执行一次）
@scheduler.scheduled_job(
    "interval", 
    minutes=1, 
    id="wumeng_monitor", 
    misfire_grace_time=10
)
async def start_monitor():
    await scheduled_ping()


# 计算正常百分比
def calculate_uptime(ping_records: List[Tuple[int, float]]) -> float:
    """计算正常响应百分比（正常次数/总次数）"""
    if not ping_records:
        return 0.0
    total = len(ping_records)
    normal = sum(1 for ts, delay in ping_records if delay != -1)
    return round((normal / total) * 100, 2)


# 图表生成函数
def generate_status_chart() -> Tuple[Optional[Path], Dict[str, float]]:
    """生成监控状态图表，返回图片路径和正常百分比字典"""
    ping_data = load_ping_data()
    addresses = load_address_config()
    uptime_dict = {}  # 存储每个地址的正常百分比

    # 计算每个地址的正常百分比
    for addr in addresses:
        records = ping_data.get(addr, [])
        uptime_dict[addr] = calculate_uptime(records)

    # 检查是否有数据
    has_data = any(len(ping_data.get(addr, [])) > 0 for addr in addresses)
    if not has_data:
        logger.warning("无监控数据，无法生成图表")
        return None, uptime_dict

    # 地址别名映射（更友好的显示名称）
    addr_alias = {
        "wechat.aime.wumeng.com": "舞萌微信AIME服务器",
        "qr.aime.wumeng.com": "玩家二维码服务器",
        "game.aime.wumeng.com": "舞萌游戏服务器",
        "www.hualixy.com": "华立官网"
    }

    # 准备图表
    fig, axes = plt.subplots(2, 2, figsize=(14, 12))
    fig.suptitle(f"舞萌服务器监控 ({datetime.now().strftime('%Y-%m-%d %H:%M')})", fontsize=16)
    axes = axes.flatten()

    # 为每个地址绘制子图
    for i, addr in enumerate(addresses):
        ax = axes[i]
        records = ping_data.get(addr, [])
        alias = addr_alias.get(addr, addr)
        uptime = uptime_dict[addr]  # 当前地址的正常百分比
        
        if not records:
            ax.text(0.5, 0.5, "暂无数据", ha="center", va="center", fontsize=12)
            ax.set_title(f"{alias}\n正常率：--", fontsize=12)
            continue

        # 提取时间和延迟数据
        timestamps, delays = zip(*records)
        times = [datetime.fromtimestamp(ts).strftime("%H:%M") for ts in timestamps]

        # 标记状态（绿色=正常，黄色=异常）
        colors = ["orange" if d == -1 else "green" for d in delays]

        # 绘制图表
        ax.plot(times, delays, marker="o", markersize=5, linestyle="-", linewidth=1.5, color="gray")
        ax.scatter(times, delays, c=colors, s=30)
        ax.set_title(f"{alias}\n正常率：{uptime}%", fontsize=12)  # 显示正常百分比
        ax.set_ylabel("延迟 (ms)", fontsize=10)
        ax.grid(True, linestyle="--", alpha=0.7)

        # 优化时间标签显示
        if len(times) > 12:
            ax.set_xticks(times[::6])
            ax.set_xticklabels(times[::6], rotation=45, ha="right", fontsize=8)
        else:
            ax.set_xticklabels(times, rotation=45, ha="right", fontsize=8)

    plt.tight_layout()
    chart_path = DATA_DIR / f"ping_chart_{int(time.time())}.png"
    plt.savefig(chart_path, dpi=200, bbox_inches="tight")
    plt.close()

    return chart_path, uptime_dict


# 命令处理器
# 1. 查看监控图表（带正常百分比）
chart_cmd = on_command(
    "监控图表",
    priority=5,
    block=True
)


@chart_cmd.handle()
async def handle_chart(bot: Bot, event: GroupMessageEvent):
    chart_path, uptime_dict = generate_status_chart()
    if not chart_path or not chart_path.exists():
        await chart_cmd.finish("暂无监控数据，稍等几分钟再试~")

    # 地址别名映射（与图表一致）
    addr_alias = {
        "wechat.aime.wumeng.com": "舞萌微信AIME服务器",
        "qr.aime.wumeng.com": "玩家二维码服务器",
        "game.aime.wumeng.com": "舞萌游戏服务器",
        "www.hualixy.com": "华立官网"
    }
    addresses = load_address_config()

    # 构建正常百分比文字说明
    uptime_text = "\n\n【今日正常率统计】\n"
    for addr in addresses:
        alias = addr_alias.get(addr, addr)
        uptime = uptime_dict.get(addr, 0.0)
        # 根据正常率添加颜色标记（绿色/黄色/红色）
        if uptime >= 90:
            uptime_text += f"✅ {alias}: {uptime}%\n"
        elif uptime >= 70:
            uptime_text += f"⚠️ {alias}: {uptime}%\n"
        else:
            uptime_text += f"❌ {alias}: {uptime}%\n"

    # 组合图片和文字消息
    reply_msg = Message(
        MessageSegment.image(chart_path) + 
        uptime_text + 
        "\n（数据每小时更新，统计最近24小时）"
    )
    await chart_cmd.finish(reply_msg)


# 2. 修改监控地址（仅管理员可用）
set_addr_cmd = on_command(
    "设置监控地址",
    priority=5,
    block=True,
    permission=SUPERUSER
)


@set_addr_cmd.handle()
async def handle_set_address(event: GroupMessageEvent):
    args = event.get_message().extract_plaintext().strip()
    
    if not args:
        current_addrs = load_address_config()
        return await set_addr_cmd.finish(
            f"当前监控地址：\n{', '.join(current_addrs)}\n\n"
            "修改格式：设置监控地址 地址1,地址2,地址3,地址4"
        )
    
    addresses = [addr.strip() for addr in args.split(",")]
    if len(addresses) != 4:
        return await set_addr_cmd.finish("必须设置4个地址，请检查格式！")
    
    try:
        save_address_config(addresses)
        return await set_addr_cmd.finish(f"已成功设置监控地址：\n{', '.join(addresses)}")
    except Exception as e:
        return await set_addr_cmd.finish(f"设置失败：{str(e)}")


# 私聊提示
private_handler = on_command(
    "监控图表",
    priority=6,
    block=True,
    permission=lambda event: isinstance(event, PrivateMessageEvent)
)


@private_handler.handle()
async def handle_private(event: PrivateMessageEvent):
    await private_handler.finish("请在群聊中使用 '监控图表' 指令查看服务器状态~")