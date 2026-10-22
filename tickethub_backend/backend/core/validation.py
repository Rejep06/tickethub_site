import hashlib
import json
from django.core.exceptions import ValidationError
import phonenumbers


def fingerprint(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':'), default=str).encode()).hexdigest()


def validate_phone(value):
    value = value.strip()
    try:
        number = phonenumbers.parse(value, None)
    except phonenumbers.NumberParseException:
        raise ValidationError('Введите телефон в международном формате, например +993…')
    if not value.startswith('+') or not phonenumbers.is_valid_number(number):
        raise ValidationError('Недопустимый международный номер телефона.')
    return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)


def clean_image(upload):
    from django.core.files import File
    from .image_processing import process_image, ImageError
    try:
        stream, name = process_image(upload, upload.size)
    except ImageError as exc:
        raise ValidationError(str(exc)) from exc
    return File(stream, name=name)


def image_from_url(url):
    from django.core.files import File
    from .image_processing import process_image, ImageError
    from .image_urls import download_image
    try:
        raw, size = download_image(url)
        try:
            stream, name = process_image(raw, size)
        finally:
            raw.close()
    except ImageError as exc:
        raise ValidationError(str(exc)) from exc
    return File(stream, name=name)
