"""
日志配置模块
"""
import logging
import os
from datetime import datetime
from typing import Optional


class Logger:
    """统一日志管理器"""
    
    _instance: Optional['Logger'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        self._initialized = True
        self.logger = None
    
    def setup(self, level: str = "INFO", log_to_file: bool = True, log_dir: str = "logs"):
        """
        初始化日志系统
        
        Args:
            level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_to_file: 是否写入文件
            log_dir: 日志目录
        """
        # 创建logger
        self.logger = logging.getLogger("nofx-python")
        self.logger.setLevel(getattr(logging, level.upper()))
        
        # 清除已有的handlers
        self.logger.handlers.clear()
        
        # 创建formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, level.upper()))
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # File handler
        if log_to_file:
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
            
            log_file = os.path.join(
                log_dir,
                f"trading_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
            )
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(getattr(logging, level.upper()))
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
            
            self.logger.info(f"✓ 日志文件创建: {log_file}")
    
    def get_logger(self) -> logging.Logger:
        """获取logger实例"""
        if self.logger is None:
            raise RuntimeError("Logger未初始化，请先调用setup()")
        return self.logger


# 全局logger实例
_logger_manager = Logger()


def setup_logger(level: str = "INFO", log_to_file: bool = True, log_dir: str = "logs"):
    """初始化日志系统"""
    _logger_manager.setup(level, log_to_file, log_dir)


def get_logger() -> logging.Logger:
    """获取logger实例"""
    return _logger_manager.get_logger()
