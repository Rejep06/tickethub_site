from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from core.serializers import StrictSerializer, StrictModelSerializer
from core.validation import validate_phone
from .models import User


class RequestCodeSerializer(StrictSerializer):
    email = serializers.EmailField()
    locale = serializers.ChoiceField(choices=['ru', 'en'], default='ru')


class VerifyCodeSerializer(RequestCodeSerializer):
    code = serializers.RegexField(r'^[0-9]{6}$')


class StaffLoginSerializer(StrictSerializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, max_length=128, trim_whitespace=False)


class ProfileSerializer(StrictModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'name', 'phone', 'locale', 'email_verified_at']
        read_only_fields = ['id', 'email', 'email_verified_at']

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Укажите имя.')
        return value

    def validate_phone(self, value):
        return validate_phone(value)


class StaffUserSerializer(StrictModelSerializer):
    password = serializers.CharField(write_only=True, required=False, trim_whitespace=False)

    class Meta:
        model = User
        fields = ['id', 'email', 'name', 'phone', 'locale', 'staff_role', 'is_active', 'password']
        read_only_fields = ['id']

    def validate(self, attrs):
        if self.instance and self.instance.is_superuser and not self.context['request'].user.is_superuser:
            raise serializers.ValidationError('Суперпользователь изменяется только суперпользователем.')
        if self.instance and 'email' in attrs and attrs['email'].lower() != self.instance.email.lower():
            raise serializers.ValidationError('Email действующего аккаунта меняется через подтверждение.')
        if not self.instance and not attrs.get('password'):
            raise serializers.ValidationError({'password': 'Задайте пароль сотрудника.'})
        if attrs.get('staff_role', getattr(self.instance, 'staff_role', '')) not in ['ADMIN', 'MANAGER']:
            raise serializers.ValidationError({'staff_role': 'Выберите ADMIN или MANAGER.'})
        if 'password' in attrs:
            validate_password(attrs['password'], self.instance or User(email=attrs.get('email', '')))
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for key, value in validated_data.items():
            setattr(instance, key, value)
        if password:
            instance.set_password(password)
        instance.full_clean()
        instance.save()
        return instance


class StartEmailChangeSerializer(StrictSerializer):
    new_email = serializers.EmailField()


class ConfirmEmailChangeSerializer(StrictSerializer):
    old_code = serializers.RegexField(r'^[0-9]{6}$')
    new_code = serializers.RegexField(r'^[0-9]{6}$')
