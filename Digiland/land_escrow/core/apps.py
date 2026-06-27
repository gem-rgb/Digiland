from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = 'core'

    def ready(self):
        # Load signal handlers so signup / email confirmation side effects
        # are wired up consistently in every process.
        import core.signals  # noqa: F401
