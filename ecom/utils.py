from functools import wraps
from django.shortcuts import redirect
from .models import User
from django.contrib import messages
from django.http import HttpResponse

def never_cache_custom(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        response = view_func(request, *args, **kwargs)
        response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        return response

    return _wrapped_view

def user_login_required(allowed_roles=None):
    """Decorator to check if user is logged in and has the required role."""
    if allowed_roles is None:
        allowed_roles = []

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            user_id = request.session.get("user_id")
            user_role = request.session.get("user_role")

            # If user is not logged in, redirect them to their respective login page
            if not user_id:
                messages.warning(request, "Please log in to access this page.")
                if "ROLE_ADMIN" in allowed_roles:
                    return redirect("login_admin")  # Admin Login
                elif "seller_owner" in allowed_roles:
                    return redirect("login_seller")  # Seller Login
                elif "ROLE_CUSTOMER" in allowed_roles:
                    return redirect("login")  # Customer Login
                return redirect("login")  # Default to customer login

            # If user does not have the required role, redirect them to their correct dashboard
            if allowed_roles and user_role not in allowed_roles:
                messages.error(request, "You do not have permission to access this page.")
                if user_role == "ROLE_ADMIN":
                    return redirect("admin_dashboard")
                elif user_role == "seller_owner":
                    return redirect("seller_dashboard")
                elif user_role == "ROLE_CUSTOMER":
                    return redirect("customer_dashboard")
                return redirect("home")  # If role doesn't match, send to home

            return view_func(request, *args, **kwargs)

        return _wrapped_view
    return decorator

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
