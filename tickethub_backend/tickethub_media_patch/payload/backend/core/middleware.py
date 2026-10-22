import uuid


class RequestIdMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Generate locally: do not trust arbitrary external header contents.
        request.request_id = str(uuid.uuid4())
        response = self.get_response(request)
        response["X-Request-ID"] = request.request_id
        return response


class PrivateResponseMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith(("/api/", "/ops/", "/health/")):
            response["Cache-Control"] = "private, no-store"
            response["X-Robots-Tag"] = "noindex, nofollow"
        if request.path.startswith(("/api/", "/health/")):
            response["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        if request.path.startswith('/media/'):
            response['X-Content-Type-Options'] = 'nosniff'
            response['Content-Security-Policy'] = "default-src 'none'; style-src 'unsafe-inline'; sandbox"
            response['Referrer-Policy'] = 'no-referrer'
            if request.path.lower().endswith('.svg'):
                response['Content-Type'] = 'image/svg+xml'

        return response


class StaffSessionTimeoutMiddleware:
    """Eight-hour staff session, thirty-minute inactivity limit; customer OTP unaffected."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        import time
        from django.contrib.auth import BACKEND_SESSION_KEY, logout
        now = int(time.time())
        backend = 'users.backends.StaffPasswordBackend'
        if request.session.get(BACKEND_SESSION_KEY) == backend and request.user.is_authenticated:
            started = request.session.get('staff_started_at', now)
            seen = request.session.get('staff_seen_at', now)
            if now - started >= 8 * 3600 or now - seen >= 30 * 60:
                logout(request)
        response = self.get_response(request)
        # Also captures the successful admin login, not just the custom API login.
        if request.session.get(BACKEND_SESSION_KEY) == backend and request.user.is_authenticated and request.user.is_staff:
            request.session.setdefault('staff_started_at', now)
            if now - request.session.get('staff_seen_at', 0) >= 60:
                request.session['staff_seen_at'] = now
            request.session.set_expiry(max(1, 8 * 3600 - (now - request.session['staff_started_at'])))
        return response
