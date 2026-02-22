
from loguru import logger

from kabot.config.schema import Config
from kabot.core.logger import configure_logger


# Mock store
class MockStore:
    def add_log(self, **kwargs):
        print(f"STORE RECEIVED: {kwargs}")

cfg = Config()
cfg.logging.level = "DEBUG"
cfg.logging.file_enabled = False # Disable file for this quick check

print("Configuring logger...")
configure_logger(cfg, MockStore())

print("Logging message...")
logger.info("Hello World")
