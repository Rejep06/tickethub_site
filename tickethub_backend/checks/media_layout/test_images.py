import io
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch
from PIL import Image
from core.image_processing import check_dimensions, process_image, sanitize_svg, ImageError, MAX_BYTES
from core.image_urls import validate_image_url, resolve_public, download_image

SVG = b'<svg xmlns="http://www.w3.org/2000/svg" width="20000" height="15000"><path d="M0 0 L20 20" fill="none" stroke="blue"/></svg>'


class ImagePolicyTests(unittest.TestCase):
    def test_exact_300mp_limit(self):
        check_dimensions(20000, 15000)

    def test_excess_pixels(self):
        with self.assertRaises(ImageError): check_dimensions(20000, 15001)

    def test_excess_side(self):
        with self.assertRaises(ImageError): check_dimensions(20001, 1)

    def test_square_20k_not_allowed(self):
        with self.assertRaises(ImageError): check_dimensions(20000, 20000)

    def test_invalid_dimensions(self):
        for size in [(0, 10), (-1, 10), (float('nan'), 10), (float('inf'), 10)]:
            with self.subTest(size=size), self.assertRaises(ImageError): check_dimensions(*size)

    def test_file_byte_limit(self):
        with self.assertRaises(ImageError): process_image(io.BytesIO(b'x'), MAX_BYTES+1)

    def test_valid_png_reencoded(self):
        source = io.BytesIO()
        Image.new('RGB', (20, 30), 'red').save(source, 'PNG')
        result, name = process_image(source, len(source.getvalue()))
        with result, Image.open(result) as img:
            self.assertEqual(img.size, (20, 30)); self.assertTrue(name.endswith('.jpg'))

    def test_transparency_preserved(self):
        source = io.BytesIO()
        Image.new('RGBA', (20, 30), (20, 30, 40, 0)).save(source, 'PNG')
        result, name = process_image(source, len(source.getvalue()))
        with result, Image.open(result) as img:
            self.assertEqual(img.getpixel((0, 0))[3], 0); self.assertTrue(name.endswith('.png'))

    def test_svg_accepted_and_rebuilt(self):
        result, name = process_image(io.BytesIO(SVG), len(SVG))
        with result:
            self.assertTrue(name.endswith('.svg'))
            root = ET.fromstring(result.read())
            self.assertEqual(root.get('width'), '20000')

    def test_svg_viewbox_only(self):
        root = ET.fromstring(sanitize_svg(b'<svg viewBox="0 0 20000 15000"><rect width="3" height="2"/></svg>'))
        self.assertEqual(root.get('width'), '20000')

    def test_svg_simple_class_styles(self):
        clean = sanitize_svg(b'<svg width="100" height="100"><style>.x {fill:#fff;stroke:red}</style><path class="x" d="M0 0"/></svg>')
        self.assertIn(b'fill:#fff;stroke:red', clean); self.assertNotIn(b'<style', clean)

    def test_svg_local_gradient(self):
        clean = sanitize_svg(b'<svg width="100" height="100"><defs><linearGradient id="g"><stop offset="0" stop-color="red"/></linearGradient></defs><rect width="20" height="20" fill="url(#g)"/></svg>')
        self.assertIn(b'url(#g)', clean)

    def test_svg_excess_pixels(self):
        with self.assertRaises(ImageError): sanitize_svg(SVG.replace(b'15000', b'15001'))

    def test_malicious_svgs_rejected(self):
        attacks = [
            b'<script>alert(1)</script>', b'<path onclick="alert(1)"/>',
            b'<foreignObject><div>html</div></foreignObject>', b'<image href="https://example.org/a.png"/>',
            b'<use href="#loop"/>', b'<style>@import "https://example.org/x";</style>',
            b'<path fill="url(https://example.org/x)"/>',
            b'<path style="fill:u\\72l(https://example.org/x)"/>',
            b'<animate attributeName="x"/>',
            b'<defs><clipPath id="c"><rect clip-path="url(#c)"/></clipPath></defs>',
        ]
        for attack in attacks:
            with self.subTest(attack=attack), self.assertRaises(ImageError):
                sanitize_svg(b'<svg width="10" height="10">' + attack + b'</svg>')

    def test_entity_blocked(self):
        with self.assertRaises(ImageError):
            sanitize_svg(b'<!DOCTYPE svg [<!ENTITY x SYSTEM "file:///etc/passwd">]><svg width="10" height="10">&x;</svg>')

    def test_non_image_rejected(self):
        with self.assertRaises(ImageError): process_image(io.BytesIO(b'not image'), 9)

    def test_svg_deep_tree(self):
        with self.assertRaises(ImageError): sanitize_svg(b'<svg width="10" height="10">' + b'<g>'*66 + b'</g>'*66 + b'</svg>')

    def test_animation_rejected(self):
        source=io.BytesIO()
        images=[Image.new('RGB',(10,10),'red'),Image.new('RGB',(10,10),'blue')]
        images[0].save(source,'WEBP',save_all=True,append_images=images[1:],duration=100)
        with self.assertRaises(ImageError):process_image(source,len(source.getvalue()))


class URLTests(unittest.TestCase):
    def test_public_https_allowed(self):
        _, host = validate_image_url('https://cdn.pbilet.com/origin/file.svg')
        self.assertEqual(host, 'cdn.pbilet.com')

    def test_unsafe_urls_rejected(self):
        for url in ['http://example.org/x', 'file:///etc/passwd', 'https://localhost/x',
                    'https://127.0.0.1/x', 'https://169.254.169.254/x', 'https://10.0.0.1/x',
                    'https://[::1]/x', 'https://[::ffff:127.0.0.1]/x', 'https://[64:ff9b::7f00:1]/x',
                    'https://user:pw@example.org/x', 'https://example.org:444/x',
                    'https://example.org/\\x', 'https://example.org/x\n', 'https://2130706433/x']:
            with self.subTest(url=url), self.assertRaises(ImageError): validate_image_url(url)

    @patch('core.image_urls.socket.getaddrinfo')
    def test_private_dns_rejected(self, lookup):
        lookup.return_value=[(2,1,6,'',('192.168.0.5',443))]
        with self.assertRaises(ImageError): resolve_public('cdn.pbilet.com')

    @patch('core.image_urls.socket.getaddrinfo')
    def test_mixed_dns_rejected(self, lookup):
        lookup.return_value=[(2,1,6,'',('1.1.1.1',443)), (2,1,6,'',('127.0.0.1',443))]
        with self.assertRaises(ImageError):resolve_public('cdn.pbilet.com')

    @patch('core.image_urls.ssl.create_default_context')
    @patch('core.image_urls.socket.socket')
    def test_connection_uses_checked_ip_and_original_tls_hostname(self, socket_mock, context):
        from core.image_urls import PinnedImageConnection
        conn=PinnedImageConnection('cdn.pbilet.com','1.1.1.1',8)
        conn.connect()
        socket_mock.return_value.connect.assert_called_once_with(('1.1.1.1',443))
        context.return_value.wrap_socket.assert_called_once_with(socket_mock.return_value,server_hostname='cdn.pbilet.com')
        conn.close()

    @patch('core.image_urls.PinnedImageConnection')
    @patch('core.image_urls.resolve_public', return_value=['1.1.1.1'])
    def test_download_checks_and_uses_public_ip(self, resolve, conn):
        response = conn.return_value.getresponse.return_value
        response.status=200
        response.getheader.side_effect=lambda key,default=None:{'Content-Type':'image/svg+xml','Content-Length':str(len(SVG))}.get(key,default)
        response.read1.side_effect=[SVG,b'']
        result,size=download_image('https://cdn.pbilet.com/file.svg')
        with result:self.assertEqual(result.read(),SVG)
        self.assertEqual(size,len(SVG))
        self.assertEqual(conn.call_args.args[:2],('cdn.pbilet.com','1.1.1.1'))

    @patch('core.image_urls.PinnedImageConnection')
    @patch('core.image_urls.resolve_public', return_value=['1.1.1.1'])
    def test_redirect_to_private_blocked(self, resolve, conn):
        response=conn.return_value.getresponse.return_value;response.status=302
        response.getheader.return_value='https://127.0.0.1/private'
        with self.assertRaises(ImageError):download_image('https://cdn.pbilet.com/file.svg')
        self.assertEqual(conn.call_count,1)

    @patch('core.image_urls.PinnedImageConnection')
    @patch('core.image_urls.resolve_public', return_value=['1.1.1.1'])
    def test_html_link_is_not_image(self, resolve, conn):
        response=conn.return_value.getresponse.return_value;response.status=200
        response.getheader.side_effect=lambda key,default=None:{'Content-Type':'text/html'}.get(key,default)
        with self.assertRaises(ImageError):download_image('https://cdn.pbilet.com/page')

    @patch('core.image_urls.PinnedImageConnection')
    @patch('core.image_urls.resolve_public', return_value=['1.1.1.1'])
    def test_oversize_response_blocked_before_read(self, resolve, conn):
        response=conn.return_value.getresponse.return_value;response.status=200
        response.getheader.side_effect=lambda key,default=None:{'Content-Type':'image/png','Content-Length':str(MAX_BYTES+1)}.get(key,default)
        with self.assertRaises(ImageError):download_image('https://cdn.pbilet.com/file.png')
        response.read1.assert_not_called()


if __name__=='__main__':unittest.main()
