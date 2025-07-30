import logging
import json

logger = logging.getLogger(__name__)


def log_debug(action: str, message: str, **kwargs):
    serialized_data = json.dumps(kwargs, ensure_ascii=False) if kwargs else ""
    logger.debug(f"[DEBUG] {action} - {message} - {serialized_data}", stacklevel=2)


def log_info(action: str, message: str, **kwargs):
    serialized_data = json.dumps(kwargs, ensure_ascii=False) if kwargs else ""
    logger.info(f"[SUCCESS] {action} - {message} - {serialized_data}", stacklevel=2)


def log_warning(action: str, message: str, **kwargs):
    serialized_data = json.dumps(kwargs, ensure_ascii=False) if kwargs else ""
    logger.warning(f"[WARNING] {action} - {message} - {serialized_data}", stacklevel=2)


def log_error(action: str, message: str, exc_info=False, **kwargs):
    serialized_data = json.dumps(kwargs, ensure_ascii=False) if kwargs else ""
    logger.error(f"[ERROR] {action} - {message} - {serialized_data}", exc_info=exc_info, stacklevel=2)
