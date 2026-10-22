import secrets
import uuid
from datetime import timedelta
from django.conf import settings
from django.contrib.auth import authenticate
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from core.errors import BusinessError, require
from .models import AuthChallenge, AuthRateLimit, User


def digest(value):
    return salted_hmac('tickethub.otp.v1', value, secret=settings.SECRET_KEY, algorithm='sha256').hexdigest()


def rate_limit(scope, email, ip, email_limit=30, ip_limit=100, window_seconds=3600):
    # Counts commit even when a later validation fails. Fixed hourly windows are
    # stored in PostgreSQL, shared by all Gunicorn workers.
    limits = sorted([(digest(f'{scope}:email:{email}'), email_limit),
                     (digest(f'{scope}:ip:{ip}'), ip_limit)])
    blocked = False
    with transaction.atomic():
        now = timezone.now()
        for key, limit in limits:
            AuthRateLimit.objects.get_or_create(key=key, defaults={'window_start': now})
            bucket = AuthRateLimit.objects.select_for_update().get(pk=key)
            if bucket.window_start + timedelta(seconds=window_seconds) <= now:
                bucket.window_start, bucket.count = now, 0
            if bucket.count >= limit:
                blocked = True
            else:
                bucket.count += 1
            bucket.save(update_fields=['window_start', 'count'])
    require(not blocked, 'RATE_LIMITED', 'Слишком много попыток. Повторите позже.', status=429)


def request_code(email, ip, locale='ru', purpose='login'):
    email = User.objects.normalize_email(email)
    rate_limit('otp-send', email, ip, 5, 30)
    with transaction.atomic():
        challenge, _ = AuthChallenge.objects.get_or_create(email=email, purpose=purpose)
        challenge = AuthChallenge.objects.select_for_update().get(pk=challenge.pk)
        now = timezone.now()
        require(not challenge.issued_at or challenge.issued_at + timedelta(seconds=60) <= now,
                'RATE_LIMITED', 'Повторная отправка доступна через 60 секунд.', status=429)
        code = f'{secrets.randbelow(1_000_000):06d}'
        challenge.nonce = uuid.uuid4()
        challenge.code_hmac = digest(f'{email}:{purpose}:{challenge.nonce}:{code}')
        challenge.issued_at = now
        challenge.expires_at = now + timedelta(minutes=10)
        challenge.attempts = 0
        challenge.consumed_at = None
        challenge.save()
        nonce = challenge.nonce
    # Never hold a transaction open while waiting for SMTP.
    try:
        sent = send_mail('Tickethub — код входа' if locale == 'ru' else 'Tickethub — sign-in code',
                         f'Код: {code}. Срок действия: 10 минут.' if locale == 'ru' else f'Code: {code}. Valid for 10 minutes.',
                         settings.DEFAULT_FROM_EMAIL, [email], fail_silently=False)
        if sent != 1:
            raise RuntimeError('Email not accepted')
    except Exception:
        AuthChallenge.objects.filter(pk=challenge.pk, nonce=nonce).update(consumed_at=timezone.now())
        raise BusinessError('EMAIL_UNAVAILABLE', 'Не удалось отправить код. Повторите позже.', status=503) from None


def consume_code(email, code, ip, purpose='login'):
    email = User.objects.normalize_email(email)
    rate_limit('otp-verify', email, ip)
    error = None
    with transaction.atomic():
        challenge = AuthChallenge.objects.select_for_update().filter(email=email, purpose=purpose).first()
        now = timezone.now()
        if not challenge or challenge.consumed_at or challenge.attempts >= 5:
            error = 'OTP_INVALID'
        elif not challenge.expires_at or challenge.expires_at <= now:
            error = 'OTP_EXPIRED'
        elif not constant_time_compare(challenge.code_hmac, digest(f'{email}:{purpose}:{challenge.nonce}:{code}')):
            challenge.attempts += 1
            challenge.save(update_fields=['attempts'])
            error = 'OTP_INVALID'
        else:
            challenge.consumed_at = now
            challenge.save(update_fields=['consumed_at'])
    # Raise only after attempts/consumption have committed.
    if error:
        raise BusinessError(error, 'Код недействителен или истёк.', status=400)
    return email


def verify_login(email, code, ip, locale='ru'):
    email = consume_code(email, code, ip)
    with transaction.atomic():
        user = User.objects.select_for_update().filter(email__iexact=email).first()
        if user is None:
            require(settings.PUBLIC_FORMS_ENABLED, 'FORMS_DISABLED', 'Регистрация временно закрыта.')
            user = User.objects.create_user(email=email, locale=locale)
        require(user.is_active, 'AUTH_REQUIRED', 'Вход недоступен.', status=401)
        if not user.email_verified_at:
            user.email_verified_at = timezone.now()
            user.save(update_fields=['email_verified_at'])
    return user


def authenticate_staff(request, email, password):
    rate_limit('staff-login', User.objects.normalize_email(email), client_ip(request), 15, 60)
    user = authenticate(request, email=email, password=password)
    require(user is not None, 'AUTH_REQUIRED', 'Неверные данные входа.', status=401)
    return user


def client_ip(request):
    if settings.TRUST_PROXY_IP:
        return request.META.get('HTTP_X_REAL_IP', request.META.get('REMOTE_ADDR', 'unknown'))
    return request.META.get('REMOTE_ADDR', 'unknown')



def start_email_change(request, new_email):
    user = request.user
    new_email = User.objects.normalize_email(new_email)
    require(user.email_verified_at is not None and new_email != user.email,
            'INVALID_EMAIL_CHANGE', 'Сначала подтвердите текущий email и укажите другой адрес.', status=400)
    require(not User.objects.filter(email__iexact=new_email).exists(),
            'EMAIL_UNAVAILABLE', 'Этот адрес нельзя использовать.', status=400)
    binding = digest(f'{user.id}:{new_email}')[:16]
    purposes = [f'change-old:{user.id}:{binding}', f'change-new:{user.id}:{binding}']
    expires = timezone.now() + timedelta(minutes=10)
    request_code(user.email, client_ip(request), user.locale, purposes[0])
    request_code(new_email, client_ip(request), user.locale, purposes[1])
    request.session['email_change'] = {'old_email': user.email, 'new_email': new_email,
        'purposes': purposes, 'expires_at': expires.timestamp()}


def confirm_email_change(request, old_code, new_code):
    pending = request.session.get('email_change')
    require(pending is not None and pending['expires_at'] > timezone.now().timestamp(),
            'EMAIL_CHANGE_EXPIRED', 'Начните подтверждение заново.', status=400)
    rate_limit('email-change-verify', request.user.email, client_ip(request))
    error = False
    with transaction.atomic():
        user = User.objects.select_for_update().get(pk=request.user.pk)
        require(user.email == pending['old_email'], 'EMAIL_CHANGED', 'Адрес уже изменён.')
        require(not User.objects.filter(email__iexact=pending['new_email']).exists(),
                'EMAIL_UNAVAILABLE', 'Этот адрес нельзя использовать.', status=400)
        pairs = [(pending['old_email'], pending['purposes'][0], old_code),
                 (pending['new_email'], pending['purposes'][1], new_code)]
        challenges = []
        now = timezone.now()
        for email, purpose, code in sorted(pairs):
            challenge = AuthChallenge.objects.select_for_update().filter(email=email, purpose=purpose).first()
            valid = bool(challenge and challenge.expires_at and challenge.expires_at > now
                         and not challenge.consumed_at and challenge.attempts < 5
                         and constant_time_compare(challenge.code_hmac, digest(f'{email}:{purpose}:{challenge.nonce}:{code}')))
            error = error or not valid
            if challenge:
                challenges.append(challenge)
        if error:
            for challenge in challenges:
                if not challenge.consumed_at:
                    challenge.attempts += 1
                    challenge.save(update_fields=['attempts'])
        else:
            for challenge in challenges:
                challenge.consumed_at = now
                challenge.save(update_fields=['consumed_at'])
            user.email = pending['new_email']
            user.email_verified_at = now
            user.save(update_fields=['email', 'email_verified_at'])
            # MVP-scale revocation: standard Django session table, no token subsystem.
            from django.contrib.sessions.models import Session
            for session in Session.objects.filter(expire_date__gt=now).exclude(session_key=request.session.session_key).iterator():
                if session.get_decoded().get('_auth_user_id') == str(user.id):
                    session.delete()
    require(not error, 'OTP_INVALID', 'Один из кодов недействителен или истёк.', status=400)
    from django.contrib.auth import update_session_auth_hash
    update_session_auth_hash(request, user)
    request.session.pop('email_change', None)
    request.user = user
    return user
