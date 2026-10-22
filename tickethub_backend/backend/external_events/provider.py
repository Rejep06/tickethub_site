"""PortalBilet endpoints come from the supplied reference, not from a verified API contract.

The adapter makes real requests. Unsupported schemas stop that import stage instead
of manufacturing seat IDs, coordinates, prices, or quantities.
"""
import re
from typing import Protocol
from urllib.parse import urlsplit, urlencode
from .http import JSONClient, JSONResponse, ProviderError

SLUG = re.compile(r'[a-z0-9]+(?:[-_][a-z0-9]+)*\Z')


def parse_event_url(value):
    try:
        parts = urlsplit(value)
        if (parts.scheme != 'https' or parts.hostname not in {'portalbilet.ru', 'www.portalbilet.ru'}
                or parts.port not in (None, 443) or parts.username is not None or parts.password is not None
                or '\\' in value or '%' in parts.path
                or any(ord(c) < 33 or ord(c) == 127 for c in value)):
            raise ValueError
        segments = parts.path.strip('/').split('/')
        if len(segments) != 2 or any(not SLUG.fullmatch(s) or len(s) > 220 for s in segments):
            raise ValueError
        city, slug = segments
    except (TypeError, ValueError, AttributeError):
        raise ProviderError('INVALID_PORTALBILET_URL', 'Нужна HTTPS-ссылка portalbilet.ru/город/мероприятие.') from None
    return city, slug, f'https://portalbilet.ru/{city}/{slug}'


def external_id(value):
    if isinstance(value, bool) or not re.fullmatch(r'[1-9][0-9]{0,29}', str(value)):
        raise ProviderError('PROVIDER_ID', 'Источник не передал корректный положительный внешний ID.')
    return str(value)


class ExternalTicketProvider(Protocol):
    """Only read methods: adding a provider does not require changing order services."""
    def fetch_event(self, url: str) -> JSONResponse: ...
    def fetch_dates(self, slug: str) -> JSONResponse: ...
    def fetch_dates_prices(self, event_source_id: str) -> JSONResponse: ...
    def fetch_hall_layout(self, hall_layout_id: str) -> JSONResponse: ...
    def fetch_tickets(self, event_source_id: str, event_date_id: str) -> JSONResponse: ...
    def fetch_standing_tickets(self, event_source_id: str, event_date_id: str) -> JSONResponse: ...


class PortalBiletProvider:
    # Implemented network reads, NOT a claim that all returned schemas are decoded.
    capabilities = ('READ_EVENT', 'FETCH_LAYOUT_JSON', 'FETCH_INVENTORY_JSON')

    def __init__(self, client=None):
        self.client = client or JSONClient()

    def fetch_event(self, url):
        city, slug, _ = parse_event_url(url)
        return self.client.get_json(
            f'https://marketplace.cdn.portalbilet.ru/root/dynamic-pages/v1/page-data/{city}/{slug}/page-data.json')

    def fetch_dates(self, slug):
        if not SLUG.fullmatch(slug):
            raise ProviderError('INVALID_SLUG', 'Некорректный slug мероприятия.')
        return self.client.get_json(f'https://api.pbilet.net/public/v1/events/{slug}/dates?source_code=market_ru')

    def fetch_dates_prices(self, event_source_id):
        return self.client.get_json('https://api.pbilet.net/public/v2/dates_prices?' + urlencode({
            'event_source_id': external_id(event_source_id), 'currency': 'RUB', 'source_id': 1}))

    def fetch_hall_layout(self, hall_layout_id):
        return self.client.get_json(f'https://tickets.api.pbilet.net/public/v1/hall-layouts/{external_id(hall_layout_id)}/coordinates')

    def fetch_tickets(self, event_source_id, event_date_id):
        return self.client.get_json('https://api.pbilet.net/public/v2/tickets?' + urlencode({
            'currency_code': 'RUB', 'lang': 'ru', 'event_source_id': external_id(event_source_id),
            'event_date_id': external_id(event_date_id), 'source_id': 1}))

    def fetch_standing_tickets(self, event_source_id, event_date_id):
        return self.client.get_json('https://tickets.api.pbilet.net/public/v2/standing_tickets?' + urlencode({
            'event_source_id': external_id(event_source_id), 'event_date_id': external_id(event_date_id),
            'currency_code': 'RUB', 'source_id': 1}))
