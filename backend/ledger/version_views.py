"""Public build metadata and authenticated-free deployment identity."""

from config.version import build_info
from django.http import JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def version(request):
    return JsonResponse(build_info())
