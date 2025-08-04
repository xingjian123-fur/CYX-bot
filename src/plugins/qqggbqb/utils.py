import os
import random
from datetime import time
from PIL import Image
from io import BytesIO

def generate_random_times(count: int = 8) -> list[time]:
    """生成指定数量的随机时间（每天）"""
    times = []
    for _ in range(count):
        # 生成0-23点的随机小时
        hour = random.randint(0, 23)
        # 生成0-59分的随机分钟
        minute = random.randint(0, 59)
        # 生成0-59秒的随机秒数
        second = random.randint(0, 59)
        times.append(time(hour, minute, second))
    # 按时间排序
    times.sort()
    return times

def get_random_image(path: str) -> tuple[Image.Image, str] | None:
    """从指定路径随机获取一张图片"""
    # 检查路径是否存在
    if not os.path.exists(path) or not os.path.isdir(path):
        return None
    
    # 获取所有图片文件
    image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp']
    image_files = []
    
    for file in os.listdir(path):
        file_path = os.path.join(path, file)
        if os.path.isfile(file_path) and os.path.splitext(file)[1].lower() in image_extensions:
            image_files.append(file_path)
    
    if not image_files:
        return None
    
    # 随机选择一张图片
    selected_file = random.choice(image_files)
    try:
        with Image.open(selected_file) as img:
            # 返回图片的副本和文件名
            return img.copy(), os.path.basename(selected_file)
    except Exception as e:
        print(f"打开图片失败: {e}")
        return None

def resize_image(image: Image.Image, target_width: int) -> Image.Image:
    """按指定宽度等比例缩小图片"""
    # 计算新高度
    width, height = image.size
    if width <= target_width:
        return image  # 如果图片宽度已经小于目标宽度，直接返回原图
    
    ratio = target_width / width
    new_height = int(height * ratio)
    
    # 调整大小
    resized_image = image.resize((target_width, new_height), Image.LANCZOS)
    return resized_image

def image_to_bytes(image: Image.Image, format: str = 'JPEG') -> BytesIO:
    """将PIL图片转换为字节流"""
    buf = BytesIO()
    # 如果是PNG且有透明通道，保持透明度
    if format == 'PNG' and image.mode in ('RGBA', 'LA'):
        image.save(buf, format=format, optimize=True)
    else:
        # 转换为RGB模式以兼容JPEG
        if image.mode in ('RGBA', 'LA'):
            background = Image.new(image.mode[:-1], image.size, (255, 255, 255))
            background.paste(image, image.split()[-1])
            image = background
        image.save(buf, format=format, quality=85, optimize=True)
    buf.seek(0)
    return buf