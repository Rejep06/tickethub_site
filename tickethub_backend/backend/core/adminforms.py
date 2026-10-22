import uuid
from django import forms
from django.utils import timezone


class VersionForm(forms.Form):
    expected_version = forms.IntegerField(widget=forms.HiddenInput, min_value=1)


class MoneyForm(VersionForm):
    idempotency_key = forms.UUIDField(widget=forms.HiddenInput, initial=uuid.uuid4)
    amount_minor = forms.IntegerField(label='Сумма в копейках', min_value=1, max_value=10**12)
    occurred_at = forms.DateTimeField(label='Фактическое время (UTC)', initial=timezone.now)
    method = forms.ChoiceField(choices=[('BANK_CARD', 'Карта'), ('SBP', 'СБП вне сайта'), ('BANK_TRANSFER', 'Перевод'), ('CASH', 'Наличные'), ('OTHER', 'Другое')])
    reference = forms.CharField(label='Подтверждение / номер операции', max_length=200)
    notes = forms.CharField(label='Внутренняя заметка', required=False, widget=forms.Textarea)


class PaymentForm(MoneyForm):
    kind = forms.ChoiceField(choices=[('PAYMENT', 'Полученная оплата'), ('DIRECT_EXPENSE', 'Прямой расход'), ('SUPPLIER_REFUND', 'Возврат от поставщика')])


class DeliveryForm(VersionForm):
    idempotency_key = forms.UUIDField(widget=forms.HiddenInput, initial=uuid.uuid4)
    recipient_email = forms.EmailField(label='Email заказа')
    sent_at = forms.DateTimeField(label='Время фактической отправки (UTC)', initial=timezone.now)
    note = forms.CharField(label='Заметка', required=False, widget=forms.Textarea)
    message_id = forms.CharField(required=False, max_length=200)
    actually_sent = forms.BooleanField(label='Я уже отправил выбранные билеты клиенту вручную')

    def __init__(self, *args, order, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['items'] = forms.ModelMultipleChoiceField(queryset=order.items.filter(is_active=True), label='Отправленные позиции')


class CancelForm(VersionForm):
    reason = forms.CharField(label='Причина', widget=forms.Textarea)
    no_pending_settlements = forms.BooleanField(label='Нет незавершённых расчётов (для освобождения неоплаченного заказа)', required=False)


class ContactForm(VersionForm):
    note = forms.CharField(label='Внутренняя заметка о контакте', required=False, widget=forms.Textarea)


class CaseDecisionForm(VersionForm):
    decision = forms.ChoiceField(choices=[('IN_PROGRESS', 'В работу'), ('NEED_INFO', 'Нужны сведения'), ('APPROVED', 'Одобрить возврат'), ('REJECTED', 'Отклонить'), ('CLOSED', 'Закрыть обычное обращение')])
    amount_minor = forms.IntegerField(label='Одобренная сумма (копейки)', min_value=1, required=False)
    public_response = forms.CharField(label='Ответ клиенту', widget=forms.Textarea)
    internal_notes = forms.CharField(label='Внутренняя заметка', required=False, widget=forms.Textarea)


class QuoteForm(VersionForm):
    together_confirmed = forms.BooleanField(required=False, label='Условие соседства мест проверено')
    expires_at = forms.DateTimeField(label='Срок предложения (UTC)')
    public_comment = forms.CharField(required=False, label='Комментарий клиенту', widget=forms.Textarea)
    override_price_minor = forms.IntegerField(required=False, min_value=1, label='Одинаковая цена билета (копейки); пусто — цены предложений')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from events.models import Event
        from tickets.models import TicketUnit
        self.fields['event'] = forms.ModelChoiceField(queryset=Event.objects.filter(status='SCHEDULED'))
        self.fields['units'] = forms.ModelMultipleChoiceField(queryset=TicketUnit.objects.filter(status='AVAILABLE').select_related('offer', 'seat'))
