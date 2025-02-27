from django.conf import settings
from django.contrib.auth import logout
from django.utils.timezone import now

class AutoLogout:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            # Get last activity time from session
            last_activity = request.session.get('last_activity')

            # If last activity exists and exceeds the limit, log the user out
            if last_activity and now().timestamp() - last_activity > settings.SESSION_COOKIE_AGE:
                logout(request)
                request.session.flush()  # Clear session

            # Update last activity timestamp
            request.session['last_activity'] = now().timestamp()

        return self.get_response(request)
