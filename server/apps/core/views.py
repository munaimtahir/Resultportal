"""Core application views."""

from django.db import connection
from django.http import JsonResponse


def healthz(request):
    """Health check endpoint for monitoring."""
    try:
        # Check database connectivity
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        
        return JsonResponse({
            "status": "ok",
            "database": "connected"
        })
    except Exception as e:
        return JsonResponse({
            "status": "error",
            "database": "disconnected",
            "error": str(e)
        }, status=500)
