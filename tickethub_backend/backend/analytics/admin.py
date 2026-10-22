from django.contrib import admin
from core.adminbase import ReadOnlyAdmin
from .models import FunnelEvent


@admin.register(FunnelEvent)
class FunnelEventAdmin(ReadOnlyAdmin):
    list_display = ['event_type', 'source', 'event', 'order', 'created_at']
    list_filter = ['event_type', 'source']
