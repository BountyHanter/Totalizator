import logging

logger = logging.getLogger(__name__)


class MaskingFilter(logging.Filter):
    """
    Фильтр для маскировки чувствительных данных.
    """
    def __init__(self, fields_to_mask=None):
        super().__init__()
        self.fields_to_mask = fields_to_mask or ['hashed_password']

    def filter(self, record):
        if hasattr(record, 'data') and isinstance(record.data, dict):
            record.data = mask_sensitive_data(record.data, fields_to_mask=self.fields_to_mask)
        return True


def mask_sensitive_data(data, fields_to_mask):
    """
    Маскирует чувствительные данные в словаре.
    """
    masked_data = data.copy()
    for field in fields_to_mask:
        if field in masked_data:
            masked_data[field] = '*****'
    return masked_data

