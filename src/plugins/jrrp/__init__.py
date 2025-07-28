from pathlib import Path
import nonebot
from nonebot import get_plugin_config
from nonebot.plugin import PluginMetadata
from .config import Config
from nonebot import on_command
import json
import random
from nonebot.matcher import Matcher 
from nonebot.adapters.onebot.v11 import Message, Event
import datetime
jrrp=''
jrrpsend=''
from nonebot.rule import startswith

__plugin_meta__ = PluginMetadata(
    name="jrrp",
    description="",
    usage="",
    config=Config,
)

config = get_plugin_config(Config)

sub_plugins = nonebot.load_plugins(
    str(Path(__file__).parent.joinpath("plugins").resolve())
)

jrrp = on_command(
	"jrrp",
	aliases={"yunqi", "运气"},
	priority=10,
	block=True
)
rule = startswith((".", "/"), ignorecase=False)

@jrrp.handle()
async def handle_function(matcher: Matcher,event: Event):
	user_id = event.get_user_id()
	today = datetime.date.today().isoformat()
	random.seed(f"{today}{user_id}")
	jrrp = (random.randint(-1, 101))
	if (10 < jrrp):
		jrrpsend=str(str("你今天的人品值是：") + str((str(jrrp) + str(",还行,放心出门吸毛"))))
	else:
		if (-1 == jrrp):
			jrrpsend=str(str("你今天的人品值是：") + str((str(jrrp) + str(" 这......完了，没救了，出门小心撞大运"))))
		else:
			jrrpsend=str(str("你今天的人品值是：") + str((str(jrrp) + str("？？？？当心手脚..."))))
	await matcher.finish(Message(jrrpsend))
	pass
