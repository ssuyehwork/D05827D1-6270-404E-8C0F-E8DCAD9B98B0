
import logging
import sys
from logging.handlers import RotatingFileHandler

def setup_logging():
    logger = logging.getLogger('RapidNotes')
    logger.setLevel(logging.DEBUG)

    # Prevent adding handlers multiple times
    if logger.hasHandlers():
        logger.handlers.clear()

    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
    )

    # Console Handler
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.DEBUG)
    stdout_handler.setFormatter(formatter)
    logger.addHandler(stdout_handler)

    # File Handler
    file_handler = RotatingFileHandler(
        'app_run.log', maxBytes=1024 * 1024 * 5, backupCount=5, encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logger.info("日志服务初始化成功。")

def get_logger(name):
    return logging.getLogger(name)

