from django.apps import AppConfig


class ExternalEventsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'external_events'
    verbose_name = 'Импорт мероприятий'
