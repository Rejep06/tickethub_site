from rest_framework.authentication import SessionAuthentication as DRFSessionAuthentication


class SessionAuthentication(DRFSessionAuthentication):
    """Keep Django sessions and CSRF; report missing login as HTTP 401."""

    def authenticate_header(self, request):
        return "Session"
