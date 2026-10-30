from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect


class AccountStandingMiddleware:
    """Log users out as soon as their account is suspended/rejected/unapproved (not at session expiry)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if user is not None and user.is_authenticated and not user.in_good_standing:
            logout(request)
            messages.error(request, 'Your account is not active. Please contact support.')
            return redirect('users:login')
        return self.get_response(request)
