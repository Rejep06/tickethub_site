"""Download one public HTTPS image, pinning validated DNS addresses to TLS connections."""
import http.client
import ipaddress
import re
import socket
import ssl
import time
from tempfile import SpooledTemporaryFile
from urllib.parse import urlsplit, urljoin
from .image_processing import ImageError, MAX_BYTES, MAX_SVG_BYTES

TYPES = {'image/jpeg', 'image/png', 'image/webp', 'image/svg+xml'}


def public_address(address):
    value = ipaddress.ip_address(address)
    if isinstance(value, ipaddress.IPv6Address):
        if value.ipv4_mapped or value.sixtofour or value.teredo or value in ipaddress.ip_network('64:ff9b::/96'):
            return False
    return value.is_global and not (value.is_multicast or value.is_unspecified or value.is_reserved or value.is_loopback or value.is_link_local)


def validate_image_url(url):
    if not isinstance(url, str) or len(url) > 2000 or '\\' in url or any(ord(c) <= 32 or ord(c) == 127 for c in url):
        raise ImageError('Некорректная ссылка на изображение.')
    try:
        parts = urlsplit(url)
        if parts.scheme != 'https' or parts.username is not None or parts.password is not None or parts.port not in (None, 443) or parts.fragment:
            raise ValueError
        host = (parts.hostname or '').encode('idna').decode('ascii').lower()
        if not host or '%' in host or host.endswith('.'):
            raise ValueError
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            if not re.fullmatch(r'(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z][a-z0-9-]{0,62}', host):
                raise ValueError
            if host.endswith(('.localhost', '.local', '.internal', '.test', '.invalid', '.example')):
                raise ValueError
        else:
            if not public_address(str(address)):
                raise ValueError
        return parts, host
    except (ValueError, UnicodeError):
        raise ImageError('Нужна прямая HTTPS-ссылка на публичное изображение без пароля и нестандартного порта.') from None


def resolve_public(host):
    try:
        answers = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        addresses = list(dict.fromkeys(answer[4][0] for answer in answers))
        if not addresses or any(not public_address(address) for address in addresses):
            raise ImageError('Ссылка ведёт в непубличную сеть. Загрузка запрещена.')
        return addresses
    except (socket.gaierror, ValueError) as exc:
        raise ImageError('Не удалось определить публичный адрес сервера изображения.') from exc


class PinnedImageConnection(http.client.HTTPSConnection):
    def __init__(self, host, address, timeout):
        super().__init__(host, timeout=timeout, context=ssl.create_default_context())
        self.address = address

    def connect(self):
        family = socket.AF_INET6 if ':' in self.address else socket.AF_INET
        raw = socket.socket(family, socket.SOCK_STREAM)
        raw.settimeout(self.timeout)
        try:
            # No second DNS resolution between validation and connect.
            raw.connect((self.address, 443))
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except Exception:
            raw.close()
            raise


def download_image(url, *, timeout=8, budget=30):
    deadline = time.monotonic() + budget

    def remaining():
        seconds = deadline - time.monotonic()
        if seconds <= 0:
            raise ImageError('Истёк срок загрузки изображения.')
        return min(timeout, seconds)

    for attempt in range(4):
        parts, host = validate_image_url(url)
        addresses = resolve_public(host)
        connection = PinnedImageConnection(host, addresses[0], remaining())
        output = None
        try:
            path = parts.path or '/'
            if parts.query:
                path += '?' + parts.query
            if not path.isascii():
                raise ImageError('Ссылка должна содержать URL-encoded путь.')
            connection.request('GET', path, headers={
                'User-Agent': 'Tickethub-ImageImport/1.0', 'Accept': ', '.join(sorted(TYPES)),
                'Accept-Encoding': 'identity',
            })
            response = connection.getresponse()
            if response.status in (301, 302, 303, 307, 308):
                location = response.getheader('Location')
                if not location or attempt == 3:
                    raise ImageError('Слишком много перенаправлений изображения.')
                url = urljoin(url, location)
                validate_image_url(url)
                continue
            if response.status != 200:
                raise ImageError(f'Сервер изображения ответил HTTP {response.status}.')
            content_type = response.getheader('Content-Type', '').split(';')[0].strip().lower()
            if content_type not in TYPES:
                raise ImageError('Ссылка вернула не PNG/JPEG/WebP/SVG. Нужен адрес самого файла, не страницы.')
            if response.getheader('Content-Encoding', 'identity').lower() not in ('identity', ''):
                raise ImageError('Сжатый HTTP-ответ изображения не поддерживается.')
            maximum = MAX_SVG_BYTES if content_type == 'image/svg+xml' else MAX_BYTES
            try:
                length = int(response.getheader('Content-Length', '0'))
            except ValueError:
                raise ImageError('Некорректный Content-Length.') from None
            if length < 0 or length > maximum:
                raise ImageError('Файл по ссылке превышает допустимый размер.')
            output = SpooledTemporaryFile(max_size=1024 * 1024, mode='w+b')
            size = 0
            while True:
                if connection.sock:
                    connection.sock.settimeout(remaining())
                # read1 avoids hiding an indefinitely slow stream inside one large read.
                block = response.read1(min(64 * 1024, maximum + 1 - size))
                remaining()
                if not block:
                    break
                size += len(block)
                if size > maximum:
                    raise ImageError('Файл по ссылке превышает допустимый размер.')
                output.write(block)
            if not size or (length and size != length):
                raise ImageError('Сервер вернул пустое или неполное изображение.')
            output.seek(0)
            result = output
            output = None
            return result, size
        except (OSError, http.client.HTTPException) as exc:
            raise ImageError('Не удалось скачать изображение по HTTPS. Проверьте доступность прямой ссылки.') from exc
        finally:
            if output is not None:
                output.close()
            connection.close()
    raise ImageError('Не удалось загрузить изображение.')
