from functools import wraps
from django.shortcuts import redirect

def never_cache_custom(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        response = view_func(request, *args, **kwargs)
        response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        return response

    return _wrapped_view

def user_login_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if 'user_id' not in request.session:
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def user(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if request.session.get('user_id'):
            return redirect('home_view')
        return view_func(request, *args, **kwargs)
    return _wrapped_view