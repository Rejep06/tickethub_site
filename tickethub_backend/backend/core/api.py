import uuid
from rest_framework.exceptions import ValidationError


def payload(serializer_class, request, **kwargs):
    serializer = serializer_class(data=request.data, context={'request': request}, **kwargs)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def idempotency_key(request):
    try:
        return uuid.UUID(request.headers.get('Idempotency-Key', ''))
    except (ValueError, AttributeError, TypeError):
        raise ValidationError({'Idempotency-Key': 'Нужен UUID в заголовке Idempotency-Key.'})
