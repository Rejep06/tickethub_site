from django.conf import settings
from .models import ContentPage, ConsentRecord
from .errors import require


def accept_documents(user, versions, source):
    # References point to published, explicitly approved versions, not invented text.
    expected = {page.slug: page for page in ContentPage.objects.filter(
        slug__in=settings.REQUIRED_LEGAL_SLUGS, is_published=True, approved_by__isnull=False)}
    if settings.REQUIRE_LEGAL_ACCEPTANCE:
        require(set(expected) == set(settings.REQUIRED_LEGAL_SLUGS),
                'LEGAL_NOT_READY', 'Приём обращений временно недоступен.', status=503)
        require(versions == {slug: page.version for slug, page in expected.items()},
                'CONSENT_REQUIRED', 'Подтвердите актуальные документы.', status=400,
                details={'versions': {slug: page.version for slug, page in expected.items()}})
    for slug, version in versions.items():
        require(slug in expected and version == expected[slug].version,
                'CONSENT_REQUIRED', 'Версия документа неактуальна.', status=400)
        ConsentRecord.objects.get_or_create(user=user, page=expected[slug], source=source)
    return dict(versions)
