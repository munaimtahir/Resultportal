"""Core application views."""

from django.db import connection
from django.http import JsonResponse
import logging

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
        logging.exception("Health check failed")
    except Exception as e:
        return JsonResponse({
            "status": "error",
            "database": "disconnected",
            "error": "An internal error occurred."
        }, status=500)
