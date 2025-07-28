from pathlib import Path

import nonebot
from nonebot import get_plugin_config
from nonebot.plugin import PluginMetadata

from .config import Config

__plugin_meta__ = PluginMetadata(
    name="help",
    description="",
    usage="",
    config=Config,
)

config = get_plugin_config(Config)

sub_plugins = nonebot.load_plugins(
    str(Path(__file__).parent.joinpath("plugins").resolve())
)

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from PIL import Image
import numpy as np

from nonebot import on_command, get_driver, logger, get_loaded_plugins
from nonebot.adapters.onebot.v11 import (
    GroupMessageEvent,
    PrivateMessageEvent,
    MessageSegment
)
from nonebot.plugin import PluginMetadata

# 插件自身元信息
__plugin_meta__ = PluginMetadata(
    name="自定义帮助插件",
    description="自动读取插件元信息，生成带自定义背景的帮助图片",
    usage="发送 '帮助' 或 '使用说明' 查看帮助图片"
)

# 路径配置
PLUGIN_DIR = Path(__file__).parent
CONFIG_FILE = PLUGIN_DIR / "help_config.json"  # 配置文件（背景设置等）
BACKGROUND_DIR = PLUGIN_DIR / "backgrounds"    # 背景图片存放目录
OUTPUT_DIR = PLUGIN_DIR / "output"              # 生成的帮助图片输出目录

# 创建必要目录
BACKGROUND_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# 确保中文正常显示
plt.rcParams["font.family"] = ["SimHei", "WenQuanYi Micro Hei", "Heiti TC"]
plt.rcParams["axes.unicode_minus"] = False  # 解决负号显示问题
plt.rcParams["savefig.dpi"] = 200  # 图片清晰度


# 配置处理类
class HelpConfig:
    """帮助插件配置结构"""
    def __init__(self):
        self.background = {
            "type": "color",       # 背景类型：color（颜色）或 image（图片）
            "value": "#f5f7fa",    # 背景值：颜色代码或图片文件名
            "opacity": 0.9         # 背景透明度（0-1）
        }
        self.show_plugins = []    # 指定显示的插件名称（空则显示全部）
        self.footer = "苍瑶bot/2025 星电"  # 底部标识文字

    @classmethod
    def from_dict(cls, data: Dict):
        """从字典加载配置"""
        config = cls()
        if "background" in data:
            config.background.update(data["background"])
        if "show_plugins" in data:
            config.show_plugins = data["show_plugins"]
        if "footer" in data:
            config.footer = data["footer"]
        return config

    def to_dict(self) -> Dict:
        """转换为字典用于保存"""
        return {
            "background": self.background,
            "show_plugins": self.show_plugins,
            "footer": self.footer
        }


# 配置加载与保存
def load_config() -> HelpConfig:
    """加载配置文件，不存在则生成默认配置"""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return HelpConfig.from_dict(json.load(f))
        except Exception as e:
            logger.error(f"加载配置失败，使用默认配置: {e}")
    
    # 生成默认配置并保存
    default_config = HelpConfig()
    save_config(default_config)
    return default_config


def save_config(config: HelpConfig):
    """保存配置到文件"""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info("配置已保存到 help_config.json")
    except Exception as e:
        logger.error(f"保存配置失败: {e}")


# 获取所有插件的元信息（兼容新版本NoneBot2）
def get_all_plugin_metas() -> List[Tuple[str, PluginMetadata]]:
    """获取已加载插件的元信息（排除自身）"""
    plugins = get_loaded_plugins()
    valid_plugins = []
    
    for plugin in plugins:
        # 直接访问plugin.metadata（新版本NoneBot2）
        meta = getattr(plugin, "metadata", None)
        # 过滤无元信息的插件和自身
        if meta and meta.name != "自定义帮助插件":
            valid_plugins.append((plugin.name, meta))
    
    # 根据配置过滤插件
    config = load_config()
    if config.show_plugins:
        valid_plugins = [
            (name, meta) for name, meta in valid_plugins 
            if meta.name in config.show_plugins
        ]
    
    return valid_plugins


# 生成帮助图片核心函数
def generate_help_image() -> Path:
    """生成带自定义背景的帮助图片，返回图片路径"""
    config = load_config()
    plugin_metas = get_all_plugin_metas()
    
    if not plugin_metas:
        raise ValueError("没有可显示的插件信息，请检查是否加载了其他插件")

    # 计算图片高度（动态适应内容）
    base_height = 2.5  # 基础高度
    plugin_height = 1.2  # 每个插件基础高度
    line_height = 0.35  # 每行文字高度
    total_height = base_height + sum(
        plugin_height + line_height * (
            len(meta.description) // 30 +  # 描述文字行数
            len(meta.usage) // 30 + 2      # 使用说明行数
        ) 
        for _, meta in plugin_metas
    )

    # 创建画布
    fig, ax = plt.subplots(figsize=(10, total_height))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, total_height)
    ax.axis("off")  # 隐藏坐标轴

    # 设置背景
    if config.background["type"] == "image":
        # 处理图片背景
        bg_filename = config.background["value"]
        bg_path = BACKGROUND_DIR / bg_filename
        
        # 检查图片是否存在
        if not bg_path.exists():
            logger.warning(f"背景图片不存在，使用默认颜色背景: {bg_path}")
            ax.set_facecolor("#f5f7fa")
        else:
            try:
                # 加载并调整背景图片
                bg_img = Image.open(bg_path).convert("RGBA")
                bg_img = bg_img.resize((1000, int(total_height * 100)), Image.LANCZOS)
                ax.imshow(bg_img, extent=[0, 10, 0, total_height], 
                          alpha=float(config.background["opacity"]))
            except Exception as e:
                logger.error(f"加载背景图片失败: {e}")
                ax.set_facecolor("#f5f7fa")
    else:
        # 纯色背景
        ax.set_facecolor(config.background["value"])

    # 绘制标题
    plt.text(
        5, total_height - 0.5, "插件帮助中心",
        fontsize=18, fontweight="bold",
        ha="center", va="center",
        bbox=dict(facecolor="white", alpha=0.8, pad=8, boxstyle="round,pad=0.5")
    )

    # 当前绘制位置（从顶部往下）
    current_y = total_height - 1.5

    # 逐个绘制插件信息
    for idx, (_, meta) in enumerate(plugin_metas, 1):
        # 插件名称
        plt.text(
            1, current_y, f"{idx}. {meta.name}",
            fontsize=14, fontweight="bold",
            ha="left", va="top",
            bbox=dict(facecolor="white", alpha=0.7, pad=5, boxstyle="round,pad=0.3")
        )
        current_y -= 0.8

        # 插件描述
        plt.text(
            1.2, current_y, "功能说明：",
            fontsize=11, fontweight="medium",
            ha="left", va="top"
        )
        current_y -= 0.5
        
        # 分行显示描述（避免过长）
        desc_lines = [
            meta.description[i:i+30] 
            for i in range(0, len(meta.description), 30)
        ]
        for line in desc_lines:
            plt.text(
                1.5, current_y, f"• {line}",
                fontsize=10,
                ha="left", va="top",
                bbox=dict(facecolor="white", alpha=0.6, pad=2, boxstyle="round,pad=0.2")
            )
            current_y -= line_height

        # 使用说明
        plt.text(
            1.2, current_y - 0.2, "使用方法：",
            fontsize=11, fontweight="medium",
            ha="left", va="top"
        )
        current_y -= 0.5
        
        # 分行显示使用说明
        usage_lines = [
            meta.usage[i:i+30] 
            for i in range(0, len(meta.usage), 30)
        ]
        for line in usage_lines:
            plt.text(
                1.5, current_y, f"• {line}",
                fontsize=10,
                ha="left", va="top",
                bbox=dict(facecolor="white", alpha=0.6, pad=2, boxstyle="round,pad=0.2")
            )
            current_y -= line_height

        # 插件间分隔
        current_y -= 0.5

    # 底部添加标识文字
    plt.text(
        5, 0.5, config.footer,
        fontsize=10, color="#666666",
        ha="center", va="center",
        bbox=dict(facecolor="white", alpha=0.8, pad=3, boxstyle="round,pad=0.3")
    )

    # 保存图片
    output_path = OUTPUT_DIR / f"help_{int(time.time())}.png"
    plt.savefig(output_path, bbox_inches="tight", pad_inches=0.5)
    plt.close()  # 释放资源

    return output_path


# 命令处理器：群聊发送帮助
help_cmd = on_command(
    "帮助",
    aliases={"使用说明", "帮助中心"},
    priority=5,
    block=True
)

@help_cmd.handle()
async def handle_group_help(event: GroupMessageEvent):
    try:
        image_path = generate_help_image()
        await help_cmd.finish(MessageSegment.image(image_path))
    except Exception as e:
        logger.error(f"群聊帮助生成失败: {e}")
        await help_cmd.finish(f"生成帮助图片失败：{str(e)}")


# 命令处理器：私聊发送帮助
private_help_cmd = on_command(
    "帮助",
    aliases={"使用说明", "帮助中心"},
    priority=6,
    block=True,
    permission=lambda e: isinstance(e, PrivateMessageEvent)
)

@private_help_cmd.handle()
async def handle_private_help(event: PrivateMessageEvent):
    try:
        image_path = generate_help_image()
        await private_help_cmd.finish(MessageSegment.image(image_path))
    except Exception as e:
        logger.error(f"私聊帮助生成失败: {e}")
        await private_help_cmd.finish(f"生成帮助图片失败：{str(e)}")


# 启动初始化
import time
async def startup_init():
    """插件启动时初始化配置"""
    load_config()
    plugins = get_all_plugin_metas()
    logger.info(f"自定义帮助插件已加载，共发现 {len(plugins)} 个插件可显示")
    logger.info(f"背景配置路径：{CONFIG_FILE}")
    logger.info("发送 '帮助' 即可查看带自定义背景的帮助图片")

get_driver().on_startup(startup_init)
