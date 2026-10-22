from django.contrib import admin
from django.urls import path
from core.adminbase import ReadOnlyAdmin, run_action
from core.admin_operation import operation_page
from core.adminforms import QuoteForm
from .models import TicketRequest, Quote, QuoteItem
from . import services


@admin.register(TicketRequest)
class RequestAdmin(ReadOnlyAdmin):
    list_display = ['number', 'custom_event_name', 'event', 'quantity', 'status', 'manager']
    list_filter = ['status', 'manager']
    search_fields = ['number', 'customer_email', 'custom_event_name']
    actions = ['start']
    change_form_template = 'admin/ticket_requests/request_change.html'

    @admin.action(description='Взять заявки в работу', permissions=['view'])
    def start(self, request, queryset):
        run_action(self, request, queryset, lambda obj: services.change_request(obj.id, request.user,
                    {'expected_version': obj.version, 'status': 'IN_PROGRESS'}))

    def get_urls(self):
        return [path('<path:object_id>/create-quote/', self.admin_site.admin_view(self.quote_view), name='ticket_requests_ticketrequest_quote')] + super().get_urls()

    def quote_view(self, request, object_id):
        from django.http import Http404
        obj = self.get_object(request, object_id)
        if obj is None:
            raise Http404
        def execute(data):
            data['event_id'] = data.pop('event').id
            price = data.pop('override_price_minor')
            data['items'] = [{'ticket_unit_id': unit.id, 'price_minor': price or unit.offer.sale_price_minor} for unit in data.pop('units')]
            from .serializers import CreateQuoteSerializer
            serializer = CreateQuoteSerializer(data=data)
            serializer.is_valid(raise_exception=True)
            services.create_quote(obj.id, request.user, serializer.validated_data)
        return operation_page(self, request, obj, 'Новое предложение (черновик)', QuoteForm, execute,
                              initial={'expected_version': obj.version, 'event': obj.event_id})


@admin.register(Quote)
class QuoteAdmin(ReadOnlyAdmin):
    list_display = ['id', 'ticket_request', 'event', 'version', 'status', 'expires_at', 'total_minor']
    list_filter = ['status']
    actions = ['send', 'withdraw']

    @admin.action(description='Отправить предложение клиенту', permissions=['view'])
    def send(self, request, queryset):
        run_action(self, request, queryset, lambda obj: services.send_quote(obj.id, request.user, obj.ticket_request.version))

    @admin.action(description='Отозвать предложение', permissions=['view'])
    def withdraw(self, request, queryset):
        run_action(self, request, queryset, lambda obj: services.withdraw_quote(obj.id, request.user, obj.ticket_request.version))


admin.site.register(QuoteItem, ReadOnlyAdmin)
