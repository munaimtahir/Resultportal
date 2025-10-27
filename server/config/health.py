"""Health check endpoint for monitoring and load balancers."""

from django.db import connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def health_check(request):
    """
    Simple health check endpoint that verifies:
    - Application is running
    - Database connection is working

    Returns 200 OK with status information.
    Returns 503 Service Unavailable if database is unreachable.
    """
    status = {
        "status": "healthy",
        "database": "connected",
    }

    try:
        # Test database connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception as e:
        status["status"] = "unhealthy"
        status["database"] = "disconnected"
        status["error"] = str(e)
        return JsonResponse(status, status=503)

    return JsonResponse(status, status=200)
