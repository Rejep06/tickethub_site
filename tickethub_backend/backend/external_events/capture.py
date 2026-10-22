"""Capture actual public provider responses for mapping, not invented test fixtures.

Can run without Django: python -m external_events.capture --url ...
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import zipfile
from .provider import PortalBiletProvider, parse_event_url
from .http import JSONClient, ProviderError
from .normalization import bootstrap, dates_list, external_id, structure, redact


def capture(url, output, max_dates=2):
    _, slug, canonical = parse_event_url(url)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError('Папка результатов не пуста. Выберите другую, чтобы не смешать два захвата.')
    provider = PortalBiletProvider(JSONClient(budget_seconds=90))
    report = {'url': canonical, 'captured_at': datetime.now(timezone.utc).isoformat(),
              'resources': {}, 'errors': [], 'mapping_verified': False}

    def fetch(name, function):
        try:
            response = function()
            payload = redact(response.payload)
            (output / f'{name}.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
            report['resources'][name] = {'url': response.url, 'sha256_before_redaction': response.sha256,
                'byte_count_before_redaction': response.byte_count, 'structure': structure(response.payload)}
            return response.payload
        except ProviderError as exc:
            report['errors'].append({'resource': name, 'code': exc.code, 'message': str(exc)})
            return None

    page = fetch('page-data', lambda: provider.fetch_event(canonical))
    try:
        if page is not None:
            event = bootstrap(page)
            dates_payload = fetch('dates', lambda: provider.fetch_dates(slug))
            try:
                dates = dates_list(dates_payload) if dates_payload is not None else dates_list(event['dates'])
            except ProviderError:
                dates = dates_list(event['dates'])
            report['provider_ids'] = {key: event[key] for key in ('external_event_id', 'event_source_id', 'external_layout_id')}
            fetch('dates-prices', lambda: provider.fetch_dates_prices(event['event_source_id']))
            if event['external_layout_id']:
                fetch('coordinates', lambda: provider.fetch_hall_layout(event['external_layout_id']))
            for row in dates[:max_dates]:
                date_id = external_id(row['id'])
                fetch(f'tickets-{date_id}', lambda: provider.fetch_tickets(event['event_source_id'], date_id))
                fetch(f'standing-{date_id}', lambda: provider.fetch_standing_tickets(event['event_source_id'], date_id))
    except ProviderError as exc:
        report['errors'].append({'resource': 'bootstrap', 'code': exc.code, 'message': str(exc)})
    report['status'] = ('CAPTURED_WITH_ERRORS' if report['resources'] else 'FAILED') if report['errors'] else 'CAPTURED'
    (output / 'manifest.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    archive = output.with_name(output.name + '.zip')
    if archive.exists():
        raise ValueError('Архив уже существует. Выберите другое имя папки результатов.')
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as zip_file:
        for path in sorted(output.glob('*.json')):
            zip_file.write(path, arcname=path.name)
    return report, archive


def main():
    parser = argparse.ArgumentParser(description='Capture public PortalBilet JSON from one event URL.')
    parser.add_argument('--url', required=True)
    parser.add_argument('--output', default='portalbilet_capture')
    parser.add_argument('--max-dates', type=int, choices=range(1, 21), default=2)
    args = parser.parse_args()
    try:
        report, archive = capture(args.url, args.output, args.max_dates)
    except (ProviderError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps({'status': report['status'], 'archive': str(archive), 'errors': report['errors']}, ensure_ascii=False, indent=2))
    return 2 if report['errors'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
