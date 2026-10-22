from django.contrib import admin
from core.adminbase import ReadOnlyAdmin
from .models import FinancialEntry


@admin.register(FinancialEntry)
class FinancialEntryAdmin(ReadOnlyAdmin):
    list_display = ['order', 'kind', 'direction', 'amount_minor', 'occurred_at', 'created_by']
    list_filter = ['kind', 'direction', 'method']
    search_fields = ['order__number', 'reference']
