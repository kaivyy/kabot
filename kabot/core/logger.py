from pathlib import Path
import sys
from loguru import logger
from kabot.config.schema import Config

class DatabaseSink:
    def __init__(self, store):
        self.store = store
    
    def write(self, message):
        record = message.record
        # Avoid recursion if logging from within store
        # But loguru usually handles this if we don't log inside the sink write method
        try:
            self.store.add_log(
                level=record["level"].name,
                module=record["name"],
                message=record["message"],
                metadata=record["extra"],
                exception=str(record["exception"]) if record["exception"] else None
            )
        except Exception:
            # Fallback to stderr if DB logging fails
            sys.stderr.write(f"Failed to log to DB: {record['message']}\n")

def configure_logger(config: Config, store=None):
    """Configure loguru logger based on settings."""
    logger.remove() # Remove default handler
    
    # Console (stderr)
    logger.add(sys.stderr, level=config.logging.level)
    
    # File
    if config.logging.file_enabled:
        path = Path(config.logging.file_path).expanduser()
        logger.add(
            path,
            rotation=config.logging.rotation,
            retention=config.logging.retention,
            level=config.logging.level,
            enqueue=True # Async safe
        )
    
    # DB
    if config.logging.db_enabled and store:
        logger.add(
            DatabaseSink(store),
            level=config.logging.level,
            serialize=False, # We handle message object directly
            enqueue=True # Async safe
        )
