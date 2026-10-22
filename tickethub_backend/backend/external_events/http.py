"""Small, read-only HTTPS client. No proxy, cookies, credentials, or arbitrary hosts."""
import hashlib
import http.client
import ipaddress
import json
import socket
import ssl
import time
from dataclasses import dataclass
from urllib.parse import urlsplit, urljoin

API_HOSTS = frozenset({
    'marketplace.cdn.portalbilet.ru', 'api.pbilet.net', 'tickets.api.pbilet.net',
})


class ProviderError(Exception):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def validate_api_url(url):
    try:
        parts = urlsplit(url)
        valid = (parts.scheme == 'https' and parts.hostname in API_HOSTS
                 and parts.port in (None, 443) and parts.username is None and parts.password is None
                 and not parts.fragment and '\\' not in url
                 and not any(ord(c) < 33 or ord(c) == 127 for c in url))
    except ValueError:
        valid = False
    if not valid:
        raise ProviderError('UNSAFE_URL', 'Запрос на этот адрес запрещён.')
    return parts


def public_ipv4_addresses(host):
    try:
        records = socket.getaddrinfo(host, 443, family=socket.AF_INET, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ProviderError('PROVIDER_DNS', 'Не удалось разрешить DNS-имя источника.') from exc
    addresses = list(dict.fromkeys(record[4][0] for record in records))
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise ProviderError('UNSAFE_ADDRESS', 'Источник разрешился в непубличный IP-адрес.')
    return addresses


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    """Connect to the checked IP, while still checking the hostname in the TLS certificate."""
    def __init__(self, host, address, timeout):
        super().__init__(host, timeout=timeout, context=ssl.create_default_context())
        self.address = address

    def connect(self):
        raw = socket.create_connection((self.address, 443), self.timeout)
        try:
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except Exception:
            raw.close()
            raise


@dataclass(frozen=True)
class JSONResponse:
    url: str
    payload: object
    sha256: str
    byte_count: int


def reject_constant(value):
    raise ValueError(f'Invalid JSON constant: {value}')


class JSONClient:
    def __init__(self, *, timeout=8, max_bytes=8 * 1024 * 1024, attempts=2, budget_seconds=90):
        self.timeout = timeout
        self.max_bytes = max_bytes
        self.attempts = attempts
        self.deadline = time.monotonic() + budget_seconds

    def remaining(self):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise ProviderError('IMPORT_TIMEOUT', 'Истёк общий срок получения данных. Повторите позже.')
        return remaining

    def get_json(self, url):
        validate_api_url(url)
        last = None
        for attempt in range(self.attempts):
            self.remaining()
            try:
                return self._fetch(url)
            except ProviderError as exc:
                last = exc
                if exc.code not in {'PROVIDER_TIMEOUT', 'PROVIDER_NETWORK', 'PROVIDER_DNS', 'PROVIDER_BUSY'}:
                    raise
                if attempt + 1 < self.attempts:
                    time.sleep(min(0.5 * 2 ** attempt, self.remaining()))
        raise last

    def _fetch(self, url):
        for redirect_count in range(3):
            parts = validate_api_url(url)
            addresses = public_ipv4_addresses(parts.hostname)
            connection = PinnedHTTPSConnection(parts.hostname, addresses[0], min(self.timeout, self.remaining()))
            try:
                path = parts.path or '/'
                if parts.query:
                    path += '?' + parts.query
                connection.request('GET', path, headers={
                    'Accept': 'application/json', 'Accept-Encoding': 'identity',
                    'User-Agent': 'Tickethub-Import/1.0',
                })
                response = connection.getresponse()
                if response.status in (301, 302, 303, 307, 308):
                    location = response.getheader('Location')
                    if not location or redirect_count == 2:
                        raise ProviderError('PROVIDER_REDIRECT', 'Слишком много перенаправлений источника.')
                    url = urljoin(url, location)
                    validate_api_url(url)
                    continue
                if response.status in (429, 500, 502, 503, 504):
                    raise ProviderError('PROVIDER_BUSY', 'Источник временно недоступен или ограничил частоту запросов.')
                if response.status != 200:
                    raise ProviderError('PROVIDER_HTTP', f'Источник ответил HTTP {response.status}.')
                content_type = response.getheader('Content-Type', '').split(';')[0].strip().lower()
                if content_type != 'application/json' and not content_type.endswith('+json'):
                    raise ProviderError('PROVIDER_CONTENT_TYPE', 'Источник вернул не JSON. Возможно, это страница защиты.')
                if response.getheader('Content-Encoding', 'identity').lower() not in ('identity', ''):
                    raise ProviderError('PROVIDER_ENCODING', 'Источник проигнорировал запрос несжатого JSON.')
                try:
                    length = int(response.getheader('Content-Length', '0'))
                except ValueError:
                    raise ProviderError('PROVIDER_LENGTH', 'Некорректный Content-Length.') from None
                if length < 0 or length > self.max_bytes:
                    raise ProviderError('PROVIDER_TOO_LARGE', 'Ответ источника превышает допустимый размер.')
                body = bytearray()
                while True:
                    if connection.sock:
                        connection.sock.settimeout(min(self.timeout, self.remaining()))
                    block = response.read(min(65536, self.max_bytes + 1 - len(body)))
                    if not block:
                        break
                    body.extend(block)
                    if len(body) > self.max_bytes:
                        raise ProviderError('PROVIDER_TOO_LARGE', 'Ответ источника превышает допустимый размер.')
                    self.remaining()
                try:
                    payload = json.loads(body.decode('utf-8-sig'), parse_constant=reject_constant)
                except (UnicodeError, ValueError, RecursionError) as exc:
                    raise ProviderError('PROVIDER_JSON', 'Источник вернул некорректный JSON.') from exc
                if not isinstance(payload, (dict, list)):
                    raise ProviderError('PROVIDER_SCHEMA', 'Корень JSON должен быть объектом или списком.')
                return JSONResponse(url, payload, hashlib.sha256(body).hexdigest(), len(body))
            except (TimeoutError, socket.timeout) as exc:
                raise ProviderError('PROVIDER_TIMEOUT', 'Истёк срок ожидания источника.') from exc
            except (OSError, http.client.HTTPException) as exc:
                raise ProviderError('PROVIDER_NETWORK', 'Не удалось получить данные по HTTPS.') from exc
            finally:
                connection.close()
        raise ProviderError('PROVIDER_REDIRECT', 'Не удалось обработать перенаправление.')
