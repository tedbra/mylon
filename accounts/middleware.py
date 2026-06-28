# accounts/middleware.py
import threading
from django.shortcuts import redirect
from django.conf import settings
from django.urls import resolve, Resolver404

_local = threading.local()

def get_current_user_campus():
    return getattr(_local, 'campus', None)

def is_current_user_director():
    return getattr(_local, 'is_director', False)


class CampusIsolationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Default states
        _local.campus = None
        _local.is_director = False

        if request.user.is_authenticated:
            try:
                profile = request.user.profile
                _local.campus = profile.campus
                _local.is_director = profile.is_director
            except Exception:
                pass

        response = self.get_response(request)
        
        # Clear storage after request lifecycle completes
        _local.campus = None
        _local.is_director = False
        return response

class GlobalLoginRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 1. If the user is authenticated, let them through immediately
        if request.user.is_authenticated:
            return self.get_response(request)

        path = request.path_info
        
        # 2. CRITICAL LOOP PROTECTION: 
        # Normalize paths by stripping trailing slashes to prevent string mismatches
        normalized_path = path.rstrip('/')
        normalized_login_url = settings.LOGIN_URL.rstrip('/')

        if normalized_path == normalized_login_url:
            return self.get_response(request)

        # 3. Resolve url names for named exceptions
        try:
            url_match = resolve(path)
            url_name = url_match.url_name
            namespace = url_match.namespace
            full_url_name = f"{namespace}:{url_name}" if namespace else url_name
        except Resolver404:
            full_url_name = None

        # Allow anyone to access the login page name or admin panel logins
        exempt_url_names = [
            'login', 
            'accounts:login',
            #'admin:login',
        ]

        # 4. Exempt static assets, media assets, and explicit login names
        if full_url_name in exempt_url_names or path.startswith('/static/') or path.startswith('/media/'):
            return self.get_response(request)

        # 5. Catch-all: If they are not logged in, bounce them to your absolute login URL
        return redirect(f"{settings.LOGIN_URL}?next={path}")

