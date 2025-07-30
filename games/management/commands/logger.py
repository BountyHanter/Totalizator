# Версия логгера 1.0
import json
import logging
import sys
from logging.handlers import RotatingFileHandler
import os

from dotenv import load_dotenv
from pythonjsonlogger import jsonlogger

load_dotenv()

LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG").upper()
valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
if LOG_LEVEL not in valid_levels:
    LOG_LEVEL = "DEBUG"


def parse_bool(val):
    return str(val).lower() in ("true", "1", "yes", "y")


# если true, то логи в консоле ведутся в формате JSON, если false - обычный текстовый лог
USE_JSON_ONLY = parse_bool(os.getenv("USE_JSON_ONLY", "true"))
# если true, то дополнительно ведётся тестовый файл логов
USE_TEXT_FILE_LOG = parse_bool(os.getenv("USE_TEXT_FILE_LOG", "false"))

# Путь к JSON фалу с логами
LOG_JSON_PATH = os.getenv("LOG_JSON_PATH", "logs/json_app.log")
# Путь к текстовому файлу с логами
LOG_FILE_PATH = os.getenv("LOG_FILE_PATH", "logs/app.log")
# Путь к файлу с логами Uvicorn
UVICORN_ERROR_LOG_PATH = os.getenv("UVICORN_ERROR_LOG_PATH", "logs/uvicorn_error.log")

# Макс размер лог файлов
try:
    MAX_LOG_SIZE_MB = int(os.getenv("MAX_LOG_SIZE_MB", "5"))
except ValueError:
    MAX_LOG_SIZE_MB = 5

# Макс кол-во файлов со старыми логами (далее идёт перезапись)
BACKUP_COUNT = 3

# Множество имён стандартных атрибутов лога, чтобы не путать с кастомными.
# СЛЕДИТЬ ЗА АКТУАЛЬНОСТЬЮ АТРИБУТОВ!!!
STANDARD_ATTRS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "message",
    "module",
    "msecs",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
    "taskName",  # начиная с Python 3.8+
}


# Расширенный JSON-форматтер (наследник из pythonjsonlogger)
class ExtraJsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        for key, value in record.__dict__.items():
            if key not in log_record:  # просто избегаем дублей
                log_record[key] = value

    def process_log_record(self, log_record):
        return json.dumps(
            log_record,
            ensure_ascii=False,
            default=getattr(self, 'json_default', None)  # если используешь кастомный fallback
        )


# Расширенный текстовый форматтер
class ExtraFormatter(logging.Formatter):
    def format(self, record):
        base_msg = super().format(record)
        extra_attrs = set(record.__dict__.keys()) - logging.LogRecord('', '', '', '', '', (), None).__dict__.keys()
        extra_attrs -= {"message"}  # избегаем дублирования
        # Всё что не входит в стандартные названия добавляется в конец
        if extra_attrs:
            extra_data = ' | '.join(f'{key}={record.__dict__[key]}' for key in sorted(extra_attrs))
            return f"{base_msg} | {extra_data}"
        return base_msg


# Используется как fallback-функция для JSON-сериализации: если какой-то объект не сериализуется в JSON
# (например, передал туда свой объект), он будет преобразован в строку
def safe_fallback(obj):
    try:
        return str(obj)
    except Exception:
        return "<not serializable>"


def configure_logger() -> logging.Logger:
    logger = logging.getLogger("app_logger")
    logger.setLevel(LOG_LEVEL)
    logger.propagate = False

    if not logger.handlers:
        # ==== Форматтеры ====
        text_formatter = ExtraFormatter(
            fmt="[%(asctime)s] [%(levelname)s] [%(module)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        json_formatter = ExtraJsonFormatter(
            fmt="%(asctime)s %(levelname)s %(name)s %(message)s %(module)s %(funcName)s %(lineno)d",
            datefmt="%Y-%m-%d %H:%M:%S",
            json_default=safe_fallback
        )

        # ==== Консольный хендлер ====
        console_handler = logging.StreamHandler(sys.stdout)
        if USE_JSON_ONLY:
            console_handler.setFormatter(json_formatter)
        else:
            console_handler.setFormatter(text_formatter)
        logger.addHandler(console_handler)

        # ==== JSON лог в файл ====
        os.makedirs(os.path.dirname(LOG_JSON_PATH), exist_ok=True)
        json_file_handler = RotatingFileHandler(
            LOG_JSON_PATH,
            maxBytes=MAX_LOG_SIZE_MB * 1024 * 1024,
            backupCount=BACKUP_COUNT,
            encoding="utf-8"
        )
        json_file_handler.setFormatter(json_formatter)
        logger.addHandler(json_file_handler)

        # ==== (опционально) текстовый лог в файл ====
        if USE_TEXT_FILE_LOG:
            os.makedirs(os.path.dirname(LOG_FILE_PATH), exist_ok=True)
            text_file_handler = RotatingFileHandler(
                LOG_FILE_PATH,
                maxBytes=MAX_LOG_SIZE_MB * 1024 * 1024,
                backupCount=BACKUP_COUNT,
                encoding="utf-8"
            )
            text_file_handler.setFormatter(text_formatter)
            logger.addHandler(text_file_handler)

    return logger


# Обёртка, для того чтобы решить проблему с конфликтными именами
class SafeLogger:
    def __init__(self, logger, standard_attrs):
        self._logger = logger
        self._standard_attrs = standard_attrs

    def _sanitize_extra(self, extra):
        if extra:
            return {(f"{k}_extra" if k in self._standard_attrs else k): v for k, v in extra.items()}
        return extra

    def debug(self, msg, *args, extra=None, **kwargs):
        self._logger.debug(msg, *args, extra=self._sanitize_extra(extra), **kwargs)

    def info(self, msg, *args, extra=None, **kwargs):
        self._logger.info(msg, *args, extra=self._sanitize_extra(extra), **kwargs)

    def warning(self, msg, *args, extra=None, **kwargs):
        self._logger.warning(msg, *args, extra=self._sanitize_extra(extra), **kwargs)

    def error(self, msg, *args, extra=None, **kwargs):
        self._logger.error(msg, *args, extra=self._sanitize_extra(extra), **kwargs)

    def critical(self, msg, *args, extra=None, **kwargs):
        self._logger.critical(msg, *args, extra=self._sanitize_extra(extra), **kwargs)

    def exception(self, msg, *args, extra=None, **kwargs):
        self._logger.exception(msg, *args, extra=self._sanitize_extra(extra), **kwargs)


log = SafeLogger(configure_logger(), STANDARD_ATTRS)


# Далее просто импортирушеь log в файлы и используешь как стандартные логгер - log.info(), log.warning() и тд


def configure_uvicorn_error_filelog():
    # Форматтер обычный, не JSON, чтобы traceback'и остались читаемыми
    error_formatter = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    os.makedirs(os.path.dirname(UVICORN_ERROR_LOG_PATH), exist_ok=True)
    file_handler = RotatingFileHandler(
        UVICORN_ERROR_LOG_PATH,
        maxBytes=MAX_LOG_SIZE_MB * 1024 * 1024,
        backupCount=BACKUP_COUNT,
        encoding="utf-8"
    )
    file_handler.setFormatter(error_formatter)
    file_handler.setLevel(logging.ERROR)  # Только ошибки
    # Добавляем к uvicorn.error
    error_logger = logging.getLogger("uvicorn.error")
    error_logger.addHandler(file_handler)
    error_logger.setLevel(logging.ERROR)
    error_logger.propagate = False


configure_uvicorn_error_filelog()
