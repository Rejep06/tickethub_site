from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
    verbose_name = "Основа проекта"


from django.contrib.admin.apps import AdminConfig


class TickethubAdminConfig(AdminConfig):
    default_site = 'core.adminsite.TickethubAdminSite'
