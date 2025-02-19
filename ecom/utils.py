from functools import wraps
from django.shortcuts import redirect
from .models import User
from django.contrib import messages
from django.http import HttpResponse

def never_cache_custom(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        response = view_func(request, *args, **kwargs)

        if not isinstance(response, HttpResponse):
            return response  # If it's not an HttpResponse, return it unchanged
        
        response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response["Pragma"] = "no-cache"
        response["Expires"] = "0"

        return response  # Return the modified response
    
    return _wrapped_view

def user_login_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if 'user_id' not in request.session:
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def user(allowed_roles=None):
    if allowed_roles is None:
        allowed_roles = []
    
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            user_id = request.session.get("user_id")
            user_role = request.session.get("user_role")
            
            if not user_id:
                messages.warning(request, "Please log in to access this page.")
                return redirect("login")
            
            if allowed_roles and user_role not in allowed_roles:
                messages.warning(request, "You do not have permission to access this page.")
                return redirect("home")
            
            return view_func(request, *args, **kwargs)
        
        return _wrapped_view
    return decorator

def check_user_exists(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.method == "POST":
            email = request.POST.get("email")
            if email and not User.objects.filter(email=email).exists():
                messages.error(request, "No account found with this email. Please register.")
                return redirect(request.path)
        return view_func(request, *args, **kwargs)
    return wrapper
