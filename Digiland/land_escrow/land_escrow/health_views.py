import io
from django.http import JsonResponse
from django.conf import settings


def health_check(request):
    """Simple health check endpoint for Docker/nginx healthchecks."""
    return JsonResponse({'status': 'healthy', 'service': 'digiland'})


def run_migrations(request):
    """One-shot migration trigger — secured by secret token in query string."""
    token = request.GET.get('token', '')
    expected = getattr(settings, 'SECRET_KEY', '')[:16]
    if not token or token != expected:
        return JsonResponse({'error': 'forbidden'}, status=403)

    from django.core.management import call_command
    out = io.StringIO()
    try:
        call_command('migrate', interactive=False, verbosity=2, stdout=out)
        return JsonResponse({'status': 'ok', 'output': out.getvalue()})
    except Exception as exc:
        return JsonResponse({'status': 'error', 'error': str(exc), 'output': out.getvalue()}, status=500)
