import logging
import os
import json
from typing import Optional, Dict, Any

DEFAULT_LOG_LEVEL = logging.INFO


class ColorFormatter(logging.Formatter):
    """带颜色的日志格式化器"""
    
    # ANSI 颜色代码
    COLORS = {
        logging.DEBUG: '\033[0;36m',  # 青色
        logging.INFO: '\033[0;32m',   # 绿色
        logging.WARNING: '\033[0;33m',# 黄色
        logging.ERROR: '\033[0;31m',  # 红色
        logging.CRITICAL: '\033[0;35m'# 紫色
    }
    RESET = '\033[0m'
    
    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelno, self.RESET)
        log_message = super().format(record)
        return f"{color}{log_message}{self.RESET}"


class JsonFormatter(logging.Formatter):
    """JSON格式的日志格式化器"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_record = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # 添加异常信息
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_record, ensure_ascii=False)


def setup_logger(
    level: int = DEFAULT_LOG_LEVEL,
    log_file: Optional[str] = None,
    formatter: Optional[logging.Formatter] = None,
    use_color: bool = True,
    use_json: bool = False,
    format_string: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
) -> None:
    """
    配置全局日志
    
    Args:
        level: 日志级别
        log_file: 日志文件路径，None表示只输出到控制台
        formatter: 日志格式化器，None使用默认格式
        use_color: 是否使用彩色输出
        use_json: 是否使用JSON格式
        format_string: 日志格式字符串
    """
    if formatter is None:
        if use_json:
            formatter = JsonFormatter(format_string)
        elif use_color:
            formatter = ColorFormatter(format_string)
        else:
            formatter = logging.Formatter(format_string)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # 清除已有的处理器
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # 文件处理器
    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        # 文件日志使用非彩色格式
        file_formatter = JsonFormatter(format_string) if use_json else logging.Formatter(format_string)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    获取日志记录器
    
    Args:
        name: 日志记录器名称，None使用根记录器
    
    Returns:
        logging.Logger: 日志记录器实例
    """
    return logging.getLogger(name)


def log_structured(logger: logging.Logger, level: int, message: str, **kwargs: Any) -> None:
    """
    记录结构化日志
    
    Args:
        logger: 日志记录器
        level: 日志级别
        message: 日志消息
        **kwargs: 额外的结构化数据
    """
    log_data = {"message": message, **kwargs}
    logger.log(level, json.dumps(log_data, ensure_ascii=False))
