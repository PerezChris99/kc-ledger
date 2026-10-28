class StaffSessionAuth:
    """Require an authenticated staff account for every private API route."""
    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated and user.is_active and user.is_staff:
            return user
        return None

staff_session_auth = StaffSessionAuth()
