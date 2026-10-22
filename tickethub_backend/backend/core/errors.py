from rest_framework.exceptions import APIException


class BusinessError(APIException):
    status_code = 409
    default_code = 'CONFLICT'

    def __init__(self, code, message, details=None, status=409):
        self.status_code = status
        self.business_code = code
        self.business_details = details or {}
        super().__init__(message, code=code)


def require(condition, code, message, *, status=409, details=None):
    if not condition:
        raise BusinessError(code, message, details=details, status=status)


def check_version(obj, expected_version):
    require(obj.version == expected_version, 'VERSION_CONFLICT',
            'Запись уже изменена. Обновите данные.', details={'version': obj.version})
