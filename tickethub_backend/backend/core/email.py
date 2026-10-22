import logging
from datetime import timedelta
from functools import partial
from django.conf import settings
from django.core.mail import EmailMessage
from django.db import transaction
from django.utils import timezone
from .models import EmailLog

logger = logging.getLogger(__name__)


def send_logged_email(log_id):
    # SMTP is always outside a database transaction; a retry can duplicate email,
    # never an order. A stale SENDING entry can be explicitly retried after 5 min.
    with transaction.atomic():
        notice = EmailLog.objects.select_for_update().get(pk=log_id)
        if notice.status == 'SENT':
            return
        if notice.status == 'SENDING' and notice.updated_at > timezone.now() - timedelta(minutes=5):
            return
        notice.status = 'SENDING'
        notice.attempts += 1
        notice.save(update_fields=['status', 'attempts', 'updated_at'])
    try:
        count = EmailMessage(notice.subject, notice.body, settings.DEFAULT_FROM_EMAIL,
                             [notice.recipient], headers={'Message-ID': f'<{notice.id}@{settings.EMAIL_MESSAGE_DOMAIN}>'}).send()
        if count != 1:
            raise RuntimeError('not accepted')
    except Exception:
        EmailLog.objects.filter(pk=log_id).update(status='FAILED', error_code='SMTP_FAILED', updated_at=timezone.now())
        logger.warning('Business email failed: %s', log_id)
    else:
        EmailLog.objects.filter(pk=log_id).update(status='SENT', error_code='', sent_at=timezone.now(), updated_at=timezone.now())


def notify(recipient, subject, body, object_id=None):
    if not recipient:
        return
    notice = EmailLog.objects.create(recipient=recipient, subject=subject, body=body, object_id=object_id)
    transaction.on_commit(partial(send_logged_email, notice.id), robust=True)
    return notice


def notify_staff(subject, object_id, *, path='/ops/', body=''):
    for address in settings.STAFF_NOTIFICATION_EMAILS:
        notify(address, subject, f'{subject}\n{body}\n{settings.SITE_URL}{path}', object_id)
