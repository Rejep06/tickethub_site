from rest_framework import serializers
from core.staff import CatalogSerializer
from core.serializers import StrictModelSerializer
from core.errors import BusinessError
from venues.serializers import VenueSerializer
from .models import Category, Participant, Event
from .services import check_orderable, save_event, save_category
from django.utils import timezone


class CategorySerializer(CatalogSerializer):
    class Meta:
        model = Category
        fields = ['id', 'slug', 'name_ru', 'name_en', 'kind', 'parent', 'is_active', 'sort_order', 'image', 'version', 'is_placeholder']
        read_only_fields = ['id', 'image', 'version', 'is_placeholder']


class StaffCategorySerializer(CategorySerializer):
    expected_version = serializers.IntegerField(write_only=True, required=False, min_value=1)

    class Meta(CategorySerializer.Meta):
        fields = [*CategorySerializer.Meta.fields, 'image_rights_source', 'image_rights_confirmed', 'expected_version']

    def create(self, validated_data):
        return save_category(None, validated_data)

    def update(self, instance, validated_data):
        return save_category(instance, validated_data)


class ParticipantSerializer(CatalogSerializer):
    class Meta:
        model = Participant
        fields = ['id', 'name_ru', 'name_en', 'kind']
        read_only_fields = ['id']


class EventSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    venue = VenueSerializer(read_only=True)
    participants = ParticipantSerializer(many=True, read_only=True)
    price_from_minor = serializers.SerializerMethodField()
    orderable = serializers.SerializerMethodField()
    delivery_due_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = Event
        fields = ['id', 'slug', 'title_ru', 'title_en', 'description_ru', 'description_en', 'category', 'venue',
                  'participants', 'start_at', 'date_tba', 'sale_deadline', 'status', 'image', 'seating_plan',
                  'fan_id_required', 'fan_id_description_ru', 'fan_id_description_en', 'refund_policy_ru',
                  'refund_policy_en', 'refund_policy_approved', 'delivery_due_at', 'price_from_minor', 'orderable', 'version']

    def get_price_from_minor(self, obj):
        if hasattr(obj, 'available_price'):
            return obj.available_price
        from tickets.services import available_units
        from django.db.models import Min
        return available_units(obj).aggregate(value=Min('offer__sale_price_minor'))['value']

    def get_orderable(self, obj):
        try:
            check_orderable(obj, timezone.now())
            return True
        except BusinessError:
            return False


class StaffEventSerializer(StrictModelSerializer):
    publication_issues = serializers.SerializerMethodField()
    expected_version = serializers.IntegerField(write_only=True, required=False, min_value=1)

    class Meta:
        model = Event
        fields = ['id', 'slug', 'title_ru', 'title_en', 'description_ru', 'description_en', 'category', 'venue',
                  'participants', 'seating_plan', 'start_at', 'date_tba', 'sale_deadline', 'status', 'visibility',
                  'is_published', 'image', 'image_rights_source', 'image_rights_confirmed', 'fan_id_required',
                  'fan_id_description_ru', 'fan_id_description_en', 'refund_policy_ru', 'refund_policy_en',
                  'refund_policy_approved', 'late_delivery_due_at', 'version', 'expected_version', 'publication_issues']
        read_only_fields = ['id', 'version', 'image', 'publication_issues']

    def get_publication_issues(self, obj):
        from django.core.exceptions import ValidationError
        # Model.clean also reports missing translations, Fan ID decisions and a draft scheme.
        published = obj.is_published
        deadline = obj.sale_deadline
        obj.is_published = True
        try:
            obj.clean()
            return {}
        except ValidationError as exc:
            return exc.message_dict if hasattr(exc, 'message_dict') else {'non_field_errors': exc.messages}
        finally:
            obj.is_published = published
            obj.sale_deadline = deadline

    def create(self, validated_data):
        return save_event(None, validated_data, self.context['request'].user)

    def update(self, instance, validated_data):
        return save_event(instance, validated_data, self.context['request'].user)
