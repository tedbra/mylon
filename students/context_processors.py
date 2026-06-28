from django.conf import settings


def global_currency_resolver(request):
    """
    Guarantees {{ currency }} is safely exposed to BOTH student and expense templates.
    """
    # 1. Fallback default if user is unauthenticated or has no campus bound
    default_symbol = getattr(settings, 'DEFAULT_CURRENCY', 'USD')
    
    if not request.user.is_authenticated:
        return {'currency': default_symbol}
        
    try:
        # 2. Try to pull the active campus currency from their profile matrix
        user_profile = request.user.profile
        
        if user_profile.campus and user_profile.campus.currency_code:
            return {'currency': user_profile.campus.currency_code}
            
    except AttributeError:
        # Handles cases where a user account might not have a profile model attached yet
        pass

    # 3. Safe fallback for global admin users looking at combined reports
    return {'currency': default_symbol}