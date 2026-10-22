from django.contrib import admin
from django.urls import path
from core.adminbase import ReadOnlyAdmin, run_action
from core.admin_operation import operation_page
from core.adminforms import PaymentForm, DeliveryForm, CancelForm, ContactForm, CaseDecisionForm, MoneyForm
from .models import Order, OrderItem, OrderHistory, CustomerCase, DeliveryRecord
from . import services


@admin.register(Order)
class OrderAdmin(ReadOnlyAdmin):
    list_display = ['number', 'customer_name', 'event', 'order_state', 'manager', 'total_minor', 'delivery_due_at']
    list_filter = ['order_state', 'event', 'manager']
    search_fields = ['number', 'customer_email', 'customer_phone']
    actions = ['start', 'confirm', 'complete']
    change_form_template = 'admin/orders/order_change.html'

    def get_urls(self):
        return [path('<path:object_id>/operation/<slug:operation>/', self.admin_site.admin_view(self.operation_view), name='orders_order_operation')] + super().get_urls()

    @admin.action(description='Взять заказы в работу', permissions=['view'])
    def start(self, request, queryset):
        run_action(self, request, queryset, lambda obj: services.start_processing_order(obj.id, request.user, obj.version))

    @admin.action(description='Подтвердить заказы', permissions=['view'])
    def confirm(self, request, queryset):
        run_action(self, request, queryset, lambda obj: services.confirm_order(obj.id, request.user, obj.version))

    @admin.action(description='Завершить исполненные заказы', permissions=['view'])
    def complete(self, request, queryset):
        run_action(self, request, queryset, lambda obj: services.complete_order(obj.id, request.user, obj.version))

    def operation_view(self, request, object_id, operation):
        from django.http import Http404
        from payments.services import record_payment
        obj = self.get_object(request, object_id)
        if obj is None:
            raise Http404
        forms = {'payment': PaymentForm, 'delivery': DeliveryForm, 'cancel': CancelForm, 'contact': ContactForm}
        if operation not in forms:
            raise Http404
        def execute(data):
            if operation == 'payment':
                record_payment(obj.id, request.user, data, data.pop('idempotency_key'))
            elif operation == 'delivery':
                data.pop('actually_sent')
                data['item_ids'] = [item.id for item in data.pop('items')]
                services.record_delivery(obj.id, request.user, data, data.pop('idempotency_key'))
            elif operation == 'cancel':
                services.cancel_order(obj.id, request.user, **data)
            else:
                services.record_contact(obj.id, request.user, **data)
        return operation_page(self, request, obj, f'Заказ {obj.number}: {operation}', forms[operation], execute,
                              initial={'expected_version': obj.version, 'recipient_email': obj.customer_email},
                              form_kwargs={'order': obj} if operation == 'delivery' else {})


@admin.register(CustomerCase)
class CaseAdmin(ReadOnlyAdmin):
    list_display = ['id', 'order', 'kind', 'status', 'approved_minor', 'created_at']
    list_filter = ['status', 'kind']
    change_form_template = 'admin/orders/case_change.html'

    def get_urls(self):
        return [path('<path:object_id>/operation/<slug:operation>/', self.admin_site.admin_view(self.operation_view), name='orders_customercase_operation')] + super().get_urls()

    def operation_view(self, request, object_id, operation):
        from django.http import Http404
        from payments.services import decide_case, record_refund
        obj = self.get_object(request, object_id)
        if obj is None or operation not in ['decision', 'settle']:
            raise Http404
        def execute(data):
            if operation == 'decision':
                decide_case(obj.id, request.user, **data)
            else:
                record_refund(obj.id, request.user, data, data.pop('idempotency_key'))
        return operation_page(self, request, obj, f'Обращение: {operation}',
                              CaseDecisionForm if operation == 'decision' else MoneyForm, execute,
                              initial={'expected_version': obj.version if operation == 'decision' else obj.order.version})


admin.site.register(OrderItem, ReadOnlyAdmin)
admin.site.register(OrderHistory, ReadOnlyAdmin)
admin.site.register(DeliveryRecord, ReadOnlyAdmin)
