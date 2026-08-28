from django.http import JsonResponse
from django.shortcuts import redirect


def home(request):
    """Public entry point for the ShopU Render web service."""
    return redirect("/miniapp/")


def health(request):
    """Render health check; deliberately does not require the database."""
    return JsonResponse({"status": "ok", "service": "shopu"})
