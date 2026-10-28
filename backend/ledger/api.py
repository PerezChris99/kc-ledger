from django.utils import timezone
from ninja import Router

router = Router()

@router.get("/health", auth=None)
def health(request):
    return {"status": "ok", "service": "kc-ledger-api", "time": timezone.now().isoformat()}

@router.get("/session")
def session_status(request):
    return {
        "authenticated": request.user.is_authenticated,
        "username": request.user.get_username() if request.user.is_authenticated else None,
    }
