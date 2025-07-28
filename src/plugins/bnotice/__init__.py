from pathlib import Path

import nonebot
from nonebot import get_plugin_config
from nonebot.plugin import PluginMetadata

from .config import Config

__plugin_meta__ = PluginMetadata(
    name="bnotice",
    description="",
    usage="",
    config=Config,
)

config = get_plugin_config(Config)

sub_plugins = nonebot.load_plugins(
    str(Path(__file__).parent.joinpath("plugins").resolve())
)

from nonebot import on_command, get_driver, logger
from nonebot.adapters.onebot.v11 import Message, GroupMessageEvent, Bot
from nonebot.params import CommandArg
from nonebot_plugin_apscheduler import scheduler
import json
import time
import requests
from pathlib import Path
from datetime import datetime

# 数据存储路径
DATA_PATH = Path(__file__).parent / "data.json"

# Bilibili API 配置
BILI_API = "https://api.bilibili.com/x/space/arc/search"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

# 数据模型：存储群聊中添加的UID及最后更新时间
class BiliData:
    def __init__(self):
        self.data = {
            "groups": {}  # 结构: {群号: {uid: {name: 昵称, last_aid: 最后视频ID, last_time: 最后检测时间}, ...}, ...}
        }
        self.load_data()

    def load_data(self):
        """从文件加载数据"""
        if DATA_PATH.exists():
            try:
                with open(DATA_PATH, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
                logger.info(f"已加载Bilibili订阅数据，共{len(self.data['groups'])}个群聊")
            except Exception as e:
                logger.error(f"加载Bilibili数据失败: {e}")

    def save_data(self):
        """保存数据到文件"""
        try:
            with open(DATA_PATH, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存Bilibili数据失败: {e}")

    def add_uid(self, group_id: str, uid: str):
        """添加UID到群聊订阅"""
        group_id = str(group_id)
        uid = str(uid)
        if group_id not in self.data["groups"]:
            self.data["groups"][group_id] = {}
        # 初始化时不设置last_aid，首次检测会自动更新
        if uid not in self.data["groups"][group_id]:
            self.data["groups"][group_id][uid] = {
                "name": "",  # 后续检测时自动获取UP主名称
                "last_aid": 0,
                "last_time": 0
            }
            self.save_data()
            return True
        return False

    def remove_uid(self, group_id: str, uid: str):
        """从群聊订阅中删除UID"""
        group_id = str(group_id)
        uid = str(uid)
        if group_id in self.data["groups"] and uid in self.data["groups"][group_id]:
            del self.data["groups"][group_id][uid]
            # 若群聊无订阅UID，删除空群条目
            if not self.data["groups"][group_id]:
                del self.data["groups"][group_id]
            self.save_data()
            return True
        return False

    def get_group_uids(self, group_id: str) -> list[str]:
        """获取群聊订阅的所有UID"""
        group_id = str(group_id)
        return list(self.data["groups"].get(group_id, {}).keys())

    def update_last_aid(self, uid: str, group_id: str, aid: int, name: str):
        """更新UID的最后视频ID和UP主名称"""
        group_id = str(group_id)
        uid = str(uid)
        if group_id in self.data["groups"] and uid in self.data["groups"][group_id]:
            self.data["groups"][group_id][uid]["last_aid"] = aid
            self.data["groups"][group_id][uid]["name"] = name
            self.data["groups"][group_id][uid]["last_time"] = int(time.time())
            self.save_data()

# 初始化数据存储
bili_data = BiliData()

# 调用Bilibili API获取最新视频
async def get_latest_video(uid: str) -> dict:
    """获取指定UID的最新视频信息"""
    try:
        params = {
            "mid": uid,
            "pn": 1,
            "ps": 1,
            "order": "pubdate"  # 按发布时间排序
        }
        response = requests.get(BILI_API, params=params, headers=HEADERS, timeout=10)
        data = response.json()
        if data.get("code") == 0 and data.get("data", {}).get("list", {}).get("vlist"):
            video = data["data"]["list"]["vlist"][0]
            return {
                "aid": video["aid"],
                "title": video["title"],
                "pubdate": video["created"],
                "url": f"https://www.bilibili.com/video/av{video['aid']}",
                "name": video["author"]
            }
        return None
    except Exception as e:
        logger.error(f"获取UID={uid}的视频失败: {e}")
        return None

# 定时检测视频更新
async def check_video_updates():
    """检测所有订阅UID的最新视频，有更新则推送"""
    logger.info("开始检测Bilibili视频更新...")
    # 遍历所有群聊的订阅UID
    for group_id in bili_data.data["groups"]:
        uids = bili_data.get_group_uids(group_id)
        for uid in uids:
            # 获取最新视频
            video = await get_latest_video(uid)
            if not video:
                continue
            # 对比最后视频ID，判断是否更新
            last_aid = bili_data.data["groups"][group_id][uid]["last_aid"]
            if video["aid"] > last_aid:
                # 有新视频，准备推送消息
                msg = (
                    f"📢 B站UP主【{video['name']}】更新啦！\n"
                    f"标题：{video['title']}\n"
                    f"链接：{video['url']}\n"
                    f"发布时间：{datetime.fromtimestamp(video['pubdate']).strftime('%Y-%m-%d %H:%M')}"
                )
                # 推送消息到对应群聊
                try:
                    bot = list(get_driver().bots.values())[0]  # 获取第一个可用机器人
                    await bot.send_group_msg(group_id=int(group_id), message=msg)
                    logger.info(f"已推送UID={uid}的新视频到群{group_id}")
                    # 更新最后视频ID
                    bili_data.update_last_aid(uid, group_id, video["aid"], video["name"])
                except Exception as e:
                    logger.error(f"推送群{group_id}消息失败: {e}")
            else:
                # 无更新，仅更新UP主名称（首次检测时会更新名称）
                bili_data.update_last_aid(uid, group_id, last_aid, video["name"])
    logger.info("Bilibili视频更新检测完成")

# 注册定时任务（每10分钟检测一次）
scheduler.add_job(
    check_video_updates,
    "interval",
    minutes=10,
    id="bilibili_update_check"
)

# 群员交互命令
# 添加UID命令
add_uid_cmd = on_command("添加uid", aliases={"绑定uid"}, priority=5)
@add_uid_cmd.handle()
async def handle_add_uid(event: GroupMessageEvent, args: Message = CommandArg()):
    uid = args.extract_plain_text().strip()
    if not uid.isdigit():
        await add_uid_cmd.finish("❌ 请输入正确的B站UID（纯数字）")
    # 添加到当前群聊的订阅
    success = bili_data.add_uid(event.group_id, uid)
    if success:
        await add_uid_cmd.finish(f"✅ 已成功添加UID={uid}的视频更新提醒，将在10分钟内首次检测")
    else:
        await add_uid_cmd.finish(f"❌ UID={uid}已在本群的提醒列表中")

# 删除UID命令
remove_uid_cmd = on_command("删除uid", aliases={"解绑uid"}, priority=5)
@remove_uid_cmd.handle()
async def handle_remove_uid(event: GroupMessageEvent, args: Message = CommandArg()):
    uid = args.extract_plain_text().strip()
    if not uid.isdigit():
        await remove_uid_cmd.finish("❌ 请输入正确的B站UID（纯数字）")
    success = bili_data.remove_uid(event.group_id, uid)
    if success:
        await remove_uid_cmd.finish(f"✅ 已成功删除UID={uid}的视频更新提醒")
    else:
        await remove_uid_cmd.finish(f"❌ UID={uid}不在本群的提醒列表中")

# 查看订阅命令
list_uid_cmd = on_command("我的uid", aliases={"订阅列表"}, priority=5)
@list_uid_cmd.handle()
async def handle_list_uid(event: GroupMessageEvent):
    uids = bili_data.get_group_uids(event.group_id)
    if not uids:
        await list_uid_cmd.finish("本群暂无订阅任何B站UID，发送「添加uid [数字]」即可订阅")
    # 补充UP主名称（若已获取）
    uid_info = []
    for uid in uids:
        name = bili_data.data["groups"][str(event.group_id)][uid]["name"] or "未知UP主"
        uid_info.append(f"• UID: {uid} 名称: {name}")
    await list_uid_cmd.finish(f"本群订阅的B站UID列表：\n" + "\n".join(uid_info))

# 插件说明命令
help_cmd = on_command("b站提醒帮助", priority=5)
@help_cmd.handle()
async def handle_help():
    help_msg = (
        "B站视频更新提醒插件使用说明：\n"
        "1. 发送「添加uid [数字]」：订阅该UID的视频更新\n"
        "2. 发送「删除uid [数字]」：取消订阅该UID\n"
        "3. 发送「订阅列表」：查看本群所有订阅的UID\n"
        "4. 系统每10分钟检测一次更新，有新视频会自动推送链接"
    )
    await help_cmd.finish(help_msg)

