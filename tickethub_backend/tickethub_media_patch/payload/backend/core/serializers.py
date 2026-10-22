from rest_framework import serializers


class ApiInfoSerializer(serializers.Serializer):
    name = serializers.CharField()
    version = serializers.CharField()
    implementation_stage = serializers.CharField()
    order_intake_enabled = serializers.BooleanField()
    online_payments_enabled = serializers.BooleanField()


class StrictInputMixin:
    def to_internal_value(self, data):
        if not hasattr(data, 'keys'):
            raise serializers.ValidationError('Ожидается JSON-объект.')
        writable = {name for name, field in self.fields.items() if not field.read_only}
        unknown = set(data.keys()) - writable
        if unknown:
            raise serializers.ValidationError({name: 'Поле не разрешено.' for name in sorted(unknown)})
        return super().to_internal_value(data)


class StrictSerializer(StrictInputMixin, serializers.Serializer):
    pass


class StrictModelSerializer(StrictInputMixin, serializers.ModelSerializer):
    pass


class VersionActionSerializer(StrictSerializer):
    expected_version = serializers.IntegerField(min_value=1)
    reason = serializers.CharField(max_length=2000, required=False, allow_blank=True, default='')


class ImageUploadSerializer(StrictSerializer):
    # Pillow's ImageField rejects SVG before our shared validator can inspect it.
    image = serializers.FileField(required=False)
    image_url = serializers.URLField(required=False, write_only=True, max_length=2000)
    rights_source = serializers.CharField(max_length=500)
    rights_confirmed = serializers.BooleanField()

    def validate_rights_confirmed(self, value):
        if not value:
            raise serializers.ValidationError('Подтвердите право использовать изображение.')
        return value

    def validate(self, attrs):
        from django.core.exceptions import ValidationError as DjangoValidationError
        from core.validation import clean_image, image_from_url
        if bool(attrs.get('image')) == bool(attrs.get('image_url')):
            raise serializers.ValidationError('Передайте ровно одно: image или image_url.')
        key = 'image_url' if attrs.get('image_url') else 'image'
        try:
            attrs['image'] = image_from_url(attrs.pop('image_url')) if key == 'image_url' else clean_image(attrs['image'])
        except DjangoValidationError as exc:
            raise serializers.ValidationError({key: exc.messages}) from exc
        return attrs
