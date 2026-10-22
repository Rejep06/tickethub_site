#!/usr/bin/env python3
"""Create secrets once. Does not overwrite an existing production configuration."""
import argparse
import os
from pathlib import Path
import re
import secrets

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('domain', help='Your canonical hostname, without https:// or a path')
args = parser.parse_args()
try:
    domain = args.domain.strip().encode('idna').decode('ascii').lower()
except UnicodeError:
    parser.error('Invalid domain')
if len(domain) > 253 or not re.fullmatch(r'(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+(?:[a-z]{2,63}|xn--[a-z0-9-]{2,59})', domain):
    parser.error('Use a public domain without scheme, port, spaces or wildcard.')
text = (ROOT / '.env.production.example').read_text()
text = text.replace('PUBLIC_HOST=example.com', 'PUBLIC_HOST=' + domain)
text = text.replace('DJANGO_SECRET_KEY=GENERATE_WITH_SCRIPT', 'DJANGO_SECRET_KEY=' + secrets.token_hex(48))
text = text.replace('POSTGRES_PASSWORD=GENERATE_WITH_SCRIPT', 'POSTGRES_PASSWORD=' + secrets.token_hex(32))
text = text.replace('POSTGRES_ADMIN_PASSWORD=GENERATE_WITH_SCRIPT', 'POSTGRES_ADMIN_PASSWORD=' + secrets.token_hex(32))
path = ROOT / '.env.production'
try:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
except FileExistsError:
    parser.error('.env.production already exists; it has NOT been overwritten.')
with os.fdopen(fd, 'w') as stream: stream.write(text)
print('Created .env.production with private permissions. Set real SMTP and contacts before enabling forms.')
