from pathlib import Path
import nonebot
from nonebot import get_plugin_config
from nonebot.plugin import PluginMetadata
from .config import Config
from nonebot import on_command
from nonebot.matcher import Matcher 
from nonebot.adapters.onebot.v11 import Message, Event

jrrpsend=''
from nonebot.rule import startswith

__plugin_meta__ = PluginMetadata(
    name="awmc",
    description="",
    usage="",
    config=Config,
)

config = get_plugin_config(Config)

sub_plugins = nonebot.load_plugins(
    str(Path(__file__).parent.joinpath("plugins").resolve())
)

awmc = on_command(
	"awmc",
	aliases={"哎舞萌吃", "哎乌蒙吃"},
	priority=10,
	block=True
)
rule = startswith((" ", ".", "/"), ignorecase=False)

@awmc.handle()
async def handle_function(matcher: Matcher,event: Event):
	awmcsend = "好你个舞萌吃，一天到晚只知道拿一个鼓鼓的包，包里面装满了手套，还提着一桶大水，仿佛机厅不下班你就不退勤，好你个舞萌吃"
	await matcher.finish(Message(awmcsend))
	pass
