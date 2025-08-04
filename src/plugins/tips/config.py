from pydantic import BaseModel


class Config(BaseModel):
    """Plugin Config Here"""



try:
    from pydantic_settings import BaseSettings
except ImportError:
    # 兼容旧版本Pydantic
    from pydantic import BaseSettings


random_suffixes: list[str] = [
    "tips：舞萌功能不需要@机器人~",
    "tips：哎，插件里面似乎隐藏了'mai什么退分'功能",
    "tips：有任何使用问题可以使用/help命令查看帮助",
    "tips：苍瑶不会主动赞你"
    ]