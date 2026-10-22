from datetime import datetime, timezone
from uuid import uuid4


def order_number():
    return f"TH-{datetime.now(timezone.utc).year}-{uuid4().hex[:12].upper()}"


def request_number():
    return f"TR-{datetime.now(timezone.utc).year}-{uuid4().hex[:12].upper()}"
