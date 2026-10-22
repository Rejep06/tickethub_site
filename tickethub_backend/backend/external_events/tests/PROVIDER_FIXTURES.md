# Provider integration tests are pending — no invented fixtures

The authoring environment could read PortalBilet's public HTML page, but could not
retrieve page-data, coordinates, dates or ticket JSON through either the web tool
or its local network. No authentic JSON fixtures were obtained.

`test_services.py` tests OUR database operations and permissions with LOCAL inputs.
It does not verify PortalBilet normalization, stable seats↔tickets IDs, monetary
units, standing inventory, or compatibility with the live provider.

Get a genuine capture:

    python manage.py capture_portalbilet --url "https://portalbilet.ru/CITY/EVENT"

After reviewing/redacting the capture, place a minimal real response sample here,
write normalization/mapping tests against it, and only then enable that import
stage. Until then it returns an explicit partial result and creates no TicketUnit.
