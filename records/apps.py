from django.apps import AppConfig
class RecordsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'records'
    def ready(self):
        from .demo import database  # noqa: F401
