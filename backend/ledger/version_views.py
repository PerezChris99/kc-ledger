"""Public build metadata and authenticated-free deployment identity."""

from django.http import JsonResponse
from django.views.decorators.http import require_GET

from config.version import build_info


@require_GET
def version(request):
    return JsonResponse(build_info())
