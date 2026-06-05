from django.http import JsonResponse


def health_check(request):
    """Simple health check endpoint for Docker/nginx healthchecks."""
    return JsonResponse({'status': 'healthy', 'service': 'digiland'})
