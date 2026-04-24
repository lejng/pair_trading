import logging
import os
import threading
from datetime import datetime
from typing import Optional

class Logger:
    """Синглтон для логирования по всему проекту"""
    _instance = None
    _lock = threading.Lock()
    _logger = None

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, logger_name: str = "logs_terminal"):
        if self._logger is None:
            self._setup_logger(logger_name=logger_name)

    def _setup_logger(self, logger_name: str, log_folder: str = "logs"):
        """Настройка логгера с файлом и консольным выводом"""

        # Создаем папку для логов
        if not os.path.exists(log_folder):
            os.makedirs(log_folder)

        # Создаем логгер
        self._logger = logging.getLogger(logger_name)
        self._logger.setLevel(logging.INFO)

        # Очищаем обработчики (чтобы избежать дублирования)
        self._logger.handlers.clear()

        # Формат с временем и потоком
        formatter = logging.Formatter(
            '%(asctime)s - %(threadName)s - %(processName)s - %(module)s - %(funcName)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # 1. Файловый обработчик
        log_file = f"{log_folder}/{logger_name}_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)

        # 2. Консольный обработчик
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)

        # Добавляем обработчики
        self._logger.addHandler(file_handler)
        self._logger.addHandler(console_handler)

    def get_logger(self) -> logging.Logger:
        """Получить экземпляр логгера"""
        return self._logger

    # Удобные методы-обертки
    def info(self, message: str, extra: Optional[dict] = None):
        """Логировать INFO сообщение"""
        if extra:
            self._logger.info(f"{message} | {extra}")
        else:
            self._logger.info(message)

    def warning(self, message: str, extra: Optional[dict] = None):
        """Логировать WARNING сообщение"""
        if extra:
            self._logger.warning(f"{message} | {extra}")
        else:
            self._logger.warning(message)

    def error(self, message: str, extra: Optional[dict] = None):
        """Логировать ERROR сообщение"""
        if extra:
            self._logger.error(f"{message} | {extra}")
        else:
            self._logger.error(message)

    def debug(self, message: str, extra: Optional[dict] = None):
        """Логировать DEBUG сообщение"""
        if extra:
            self._logger.debug(f"{message} | {extra}")
        else:
            self._logger.debug(message)


# Глобальный экземпляр для удобного использования
logger_instance = Logger()