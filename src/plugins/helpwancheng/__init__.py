from pathlib import Path

import nonebot
from nonebot import get_plugin_config
from nonebot.plugin import PluginMetadata

from .config import Config

__plugin_meta__ = PluginMetadata(
    name="helpwancheng",
    description="",
    usage="",
    config=Config,
)

config = get_plugin_config(Config)

sub_plugins = nonebot.load_plugins(
    str(Path(__file__).parent.joinpath("plugins").resolve())
)

import os
import traceback
from PIL import Image, ImageDraw, ImageFont
from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, MessageSegment
from nonebot.log import logger
from nonebot.exception import FinishedException

# 帮助命令
help_cmd = on_command("完成表帮助", aliases={"helpwancheng"}, priority=5, block=True)

@help_cmd.handle()
async def handle_help(bot: Bot, event: MessageEvent):
    try:
        logger.info("开始生成帮助图片...")
        
        # 读取帮助文本
        current_dir = os.path.dirname(os.path.abspath(__file__))
        help_text_path = os.path.join(current_dir, "helptext.txt")
        
        # 检查帮助文本文件是否存在
        if not os.path.exists(help_text_path):
            raise FileNotFoundError(f"帮助文本文件不存在: {help_text_path}")
        
        with open(help_text_path, "r", encoding="utf-8") as f:
            help_text = f.read()
        
        if not help_text.strip():
            raise ValueError("帮助文本内容为空")
        
        # 生成帮助图片
        image_path = generate_help_image(help_text)
        
        # 检查生成的图片是否存在
        if not os.path.exists(image_path):
            raise FileNotFoundError("生成的帮助图片不存在")
        
        # 发送帮助图片
        logger.info(f"帮助图片生成成功，准备发送: {image_path}")
        await help_cmd.finish(MessageSegment.image(file=image_path))
        
    # 排除框架的正常终止信号，不处理
    except FinishedException:
        raise  # 让框架正常终止事件
    
    # 只处理真正的错误（文件问题、图片生成失败等）
    except Exception as e:
        # 记录详细的错误堆栈信息
        error_msg = f"生成帮助图片失败: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        await help_cmd.finish(error_msg)

def generate_help_image(text: str) -> str:
    """生成带背景的帮助图片"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 背景图片路径
    background_path = os.path.join(current_dir, "background.png")
    
    # 检查背景图片是否存在，不存在则使用默认
    if not os.path.exists(background_path):
        logger.warning(f"自定义背景图片不存在: {background_path}，将使用默认背景")
        background_path = os.path.join(current_dir, "default_background.png")
        
        # 如果默认背景也不存在，创建一个简单的背景
        if not os.path.exists(background_path):
            logger.info("默认背景图片不存在，创建简单背景")
            try:
                img = Image.new("RGB", (800, 600), color=(240, 240, 240))
                draw = ImageDraw.Draw(img)
                draw.rectangle([50, 50, 750, 550], outline=(0, 0, 0), width=2)
                img.save(background_path)
                logger.info(f"简单背景创建成功: {background_path}")
            except Exception as e:
                logger.error(f"创建简单背景失败: {str(e)}")
                raise
    
    # 打开背景图片
    try:
        background = Image.open(background_path).convert("RGBA")
        logger.info(f"成功加载背景图片: {background_path}")
    except Exception as e:
        logger.error(f"加载背景图片失败: {str(e)}，使用默认纯色背景")
        background = Image.new("RGBA", (800, 600), color=(240, 240, 240))
    
    # 创建绘图对象
    draw = ImageDraw.Draw(background)
    
    # 设置字体
    font_path = find_font_path()
    if font_path:
        logger.info(f"找到可用字体: {font_path}")
        try:
            font = ImageFont.truetype(font_path, 24)
        except Exception as e:
            logger.error(f"加载字体失败: {str(e)}，使用默认字体")
            font = ImageFont.load_default()
    else:
        logger.warning("未找到可用字体，使用默认字体")
        font = ImageFont.load_default()
    
    # 文本框设置
    margin = 60
    max_width = background.width - margin * 2
    max_height = background.height - margin * 2
    
    # 处理文本换行
    wrapped_text = wrap_text(text, font, max_width)
    
    # 计算文本整体宽度和高度
    text_bbox = draw.multiline_textbbox((0, 0), wrapped_text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    
    # 计算文本起始位置（水平和垂直双向居中）
    x_position = (background.width - text_width) // 2
    y_position = (background.height - text_height) // 2
    
    # 绘制居中的文本
    draw.multiline_text((x_position, y_position), wrapped_text, font=font, 
                        fill=(0, 0, 0), align="center")
    
    # 保存生成的图片
    output_path = os.path.join(current_dir, "help_output.png")
    try:
        background.save(output_path)
        logger.info(f"帮助图片保存成功: {output_path}")
        return output_path
    except Exception as e:
        logger.error(f"保存帮助图片失败: {str(e)}")
        raise

def wrap_text(text: str, font: ImageFont, max_width: int) -> str:
    """根据最大宽度对文本进行换行处理"""
    lines = []
    for paragraph in text.split('\n'):
        if not paragraph:
            lines.append('')
            continue
            
        words = paragraph.split(' ')
        line = words[0]
        for word in words[1:]:
            test_line = line + ' ' + word
            bbox = font.getbbox(test_line) if hasattr(font, 'getbbox') else font.getsize(test_line)
            line_width = bbox[2] - bbox[0] if len(bbox) == 4 else bbox[0]
            if line_width <= max_width:
                line = test_line
            else:
                lines.append(line)
                line = word
        lines.append(line)
    return '\n'.join(lines)

def find_font_path() -> str:
    """查找可用的字体文件"""
    # 常用字体路径
    font_paths = [
        "C:/Windows/Fonts/simhei.ttf",       # Windows 黑体
        "/System/Library/Fonts/PingFang.ttc",  # macOS
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",  # Linux
    ]
    
    # 检查字体文件是否存在
    for font_path in font_paths:
        if os.path.exists(font_path):
            return font_path
    
    # 如果没有找到任何字体，返回None将使用默认字体
    return None