"""Generic transport/security tests, NOT invented PortalBilet response fixtures."""
import json
import socket
import unittest
from unittest.mock import patch
from external_events.http import JSONClient, ProviderError, validate_api_url, public_ipv4_addresses
from external_events.provider import parse_event_url, PortalBiletProvider, external_id


class URLTests(unittest.TestCase):
    def test_canonical_url(self):
        self.assertEqual(parse_event_url('https://portalbilet.ru/sochi/test-event/'),
                         ('sochi','test-event','https://portalbilet.ru/sochi/test-event'))

    def test_tracking_not_forwarded(self):
        self.assertEqual(parse_event_url('https://www.portalbilet.ru/sochi/test?utm_source=x#tickets')[2],
                         'https://portalbilet.ru/sochi/test')

    def test_unsafe_inputs(self):
        values=['http://portalbilet.ru/sochi/test','https://127.0.0.1/a/b','file:///etc/passwd',
                'https://portalbilet.ru.evil.test/a/b','https://portalbilet.ru@evil.test/a/b',
                'https://evil.test@portalbilet.ru/a/b','https://portalbilet.ru:8080/a/b',
                'https://portalbilet.ru/a/../b','https://portalbilet.ru/a/%2e%2e',
                'https://portalbilet.ru/a%2fb/c','https://portalbilet.ru./a/b',
                'https://portalbilet.ru/a/b\\c','https://portalbilet.ru/a/b\n',None]
        for value in values:
            with self.subTest(value=value),self.assertRaises(ProviderError):parse_event_url(value)

    def test_api_allowlist(self):
        self.assertEqual(validate_api_url('https://api.pbilet.net/public/v1/x').hostname,'api.pbilet.net')
        for url in ['https://api.pbilet.net.evil.test/a','http://api.pbilet.net/a','https://api.pbilet.net:8443/a','https://localhost/a']:
            with self.subTest(url=url),self.assertRaises(ProviderError):validate_api_url(url)

    def test_id_path_injection(self):
        for value in ['../1','1&x=2',True,0,-3,'1/2',None]:
            with self.subTest(value=value),self.assertRaises(ProviderError):external_id(value)

    def test_ipv4_private_rejected(self):
        for address in ['127.0.0.1','10.0.0.1','169.254.169.254','192.168.1.1','172.16.0.1','0.0.0.0']:
            with patch('external_events.http.socket.getaddrinfo',return_value=[(socket.AF_INET,socket.SOCK_STREAM,6,'',(address,443))]):
                with self.subTest(address=address),self.assertRaises(ProviderError):public_ipv4_addresses('api.pbilet.net')

    def test_mixed_private_public_dns_rejected(self):
        records=[(socket.AF_INET,socket.SOCK_STREAM,6,'',(address,443)) for address in ['1.1.1.1','127.0.0.1']]
        with patch('external_events.http.socket.getaddrinfo',return_value=records),self.assertRaises(ProviderError):public_ipv4_addresses('api.pbilet.net')

    def test_empty_dns_rejected(self):
        with patch('external_events.http.socket.getaddrinfo',return_value=[]),self.assertRaises(ProviderError):public_ipv4_addresses('api.pbilet.net')

    def test_public_dns(self):
        with patch('external_events.http.socket.getaddrinfo',return_value=[(socket.AF_INET,socket.SOCK_STREAM,6,'',('1.1.1.1',443))]):
            self.assertEqual(public_ipv4_addresses('api.pbilet.net'),['1.1.1.1'])

    def test_endpoint_builder_uses_input_ids(self):
        class Recorder:
            def get_json(self,url):return url
        provider=PortalBiletProvider(Recorder())
        self.assertIn('/hall-layouts/123/coordinates',provider.fetch_hall_layout('123'))
        self.assertIn('event_date_id=789',provider.fetch_tickets('456','789'))
        self.assertIn('event_source_id=456',provider.fetch_standing_tickets('456','789'))
        self.assertNotIn('HOLD',provider.capabilities)


class FakeResponse:
    def __init__(self,status=200,body=b'{}',headers=None):
        self.status,self.body,self.headers=status,body,headers or {'Content-Type':'application/json'}
    def getheader(self,name,default=None):return self.headers.get(name,default)
    def read(self,size):
        result,self.body=self.body[:size],self.body[size:]
        return result


class TransportTests(unittest.TestCase):
    def fetch(self,response,limit=1000):
        class FakeConnection:
            sock=None
            def __init__(self,*args,**kwargs):pass
            def request(self,*args,**kwargs):pass
            def getresponse(self):return response
            def close(self):pass
        with patch('external_events.http.public_ipv4_addresses',return_value=['1.1.1.1']),patch('external_events.http.PinnedHTTPSConnection',FakeConnection):
            return JSONClient(attempts=1,max_bytes=limit).get_json('https://api.pbilet.net/public/test')

    def test_generic_json(self):
        result=self.fetch(FakeResponse(body=b'{"number":7}'))
        self.assertEqual(result.payload,{'number':7})
        self.assertEqual(len(result.sha256),64)

    def test_block_html(self):
        with self.assertRaises(ProviderError) as raised:self.fetch(FakeResponse(headers={'Content-Type':'text/html'}))
        self.assertEqual(raised.exception.code,'PROVIDER_CONTENT_TYPE')

    def test_size_limit_without_length(self):
        with self.assertRaises(ProviderError) as raised:self.fetch(FakeResponse(body=b'x'*1001),1000)
        self.assertEqual(raised.exception.code,'PROVIDER_TOO_LARGE')

    def test_size_limit_with_length(self):
        with self.assertRaises(ProviderError):self.fetch(FakeResponse(headers={'Content-Type':'application/json','Content-Length':'99999'}))

    def test_malformed_json(self):
        with self.assertRaises(ProviderError):self.fetch(FakeResponse(body=b'{broken'))

    def test_nan_rejected(self):
        with self.assertRaises(ProviderError):self.fetch(FakeResponse(body=b'{"x":NaN}'))

    def test_redirect_unknown_host(self):
        with self.assertRaises(ProviderError) as raised:self.fetch(FakeResponse(status=302,headers={'Location':'https://evil.test/a'}))
        self.assertEqual(raised.exception.code,'UNSAFE_URL')

    def test_gzip_not_decompressed_unbounded(self):
        with self.assertRaises(ProviderError):self.fetch(FakeResponse(headers={'Content-Type':'application/json','Content-Encoding':'gzip'}))

    def test_status_error(self):
        with self.assertRaises(ProviderError):self.fetch(FakeResponse(status=404))

    def test_budget_expires(self):
        client=JSONClient(budget_seconds=-1)
        with self.assertRaises(ProviderError) as raised:client.get_json('https://api.pbilet.net/public/test')
        self.assertEqual(raised.exception.code,'IMPORT_TIMEOUT')

    def test_retries_transient_but_not_schema_errors(self):
        client=JSONClient(attempts=2)
        error=ProviderError('PROVIDER_TIMEOUT','Timeout')
        with patch.object(client,'_fetch',side_effect=error) as fetch,patch('external_events.http.time.sleep') as sleep:
            with self.assertRaises(ProviderError):client.get_json('https://api.pbilet.net/public/test')
            self.assertEqual(fetch.call_count,2)
            self.assertEqual(sleep.call_count,1)
        with patch.object(client,'_fetch',side_effect=ProviderError('PROVIDER_JSON','bad')) as fetch:
            with self.assertRaises(ProviderError):client.get_json('https://api.pbilet.net/public/test')
            self.assertEqual(fetch.call_count,1)
