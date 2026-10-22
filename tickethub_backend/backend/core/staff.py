from django.db import transaction
from rest_framework import mixins, viewsets
from core.permissions import IsStaff
from core.serializers import StrictModelSerializer


class CatalogSerializer(StrictModelSerializer):
    """Plain model validation for small dictionaries (not orders/inventory)."""
    def create(self, validated_data):
        obj = self.Meta.model(**validated_data)
        obj.full_clean()
        obj.save()
        return obj

    def update(self, instance, validated_data):
        with transaction.atomic():
            instance = self.Meta.model.objects.select_for_update().get(pk=instance.pk)
            for key, value in validated_data.items():
                setattr(instance, key, value)
            instance.full_clean()
            instance.save()
        return instance


class CatalogViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin,
                     mixins.CreateModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsStaff]
    http_method_names = ['get', 'post', 'patch', 'head', 'options']
