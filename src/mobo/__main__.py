from .client import Mobo
from .config import MoboConfig

cfg = MoboConfig.from_env()
Mobo(cfg).run()
