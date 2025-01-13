from django.shortcuts import render, redirect
from .models import Product, User, Contact, About, CartItem, Cart, Order, OrderItem, BillingAddress, Payment, UserRole
from django.contrib.auth.hashers import make_password, check_password
from .utils import never_cache_custom, user, user_login_required
from django.http import JsonResponse, HttpResponseNotAllowed
import json
from django.db.models import F

# Helper function to handle user registration
def register_user(request, role, template, redirect_url):
    if request.method == "POST":
        name = request.POST.get("name")
        email = request.POST.get("email")
        phone = request.POST.get("phone")
        password = request.POST.get("password")
        gender = request.POST.get("gender")

        # Check if the user already exists
        if User.objects.filter(email=email, role=role).exists():
            context = {
                "name": name,
                "phone": phone,
                "gender": gender,
                "error": "Email already registered."
            }
            return render(request, template, context)

        # Create and save the user
        hashed_password = make_password(password)
        User.objects.create(
            name=name, email=email, phone=phone, 
            password=hashed_password, gender=gender, role=role
        )

        return redirect(redirect_url)

    return render(request, template)

# Registration views for different roles
@never_cache_custom
@user
def register_customer(request):
    return register_user(request, UserRole.CUSTOMER, "product_details/register.html", "login")

@never_cache_custom
@user
def register_seller(request):
    return register_user(request, UserRole.SELLER_OWNER, "seller/register.html", "login_seller")

@never_cache_custom
@user
def register_admin(request):
    return register_user(request, UserRole.ADMIN, "admin/register.html", "login_admin")

# Helper function for user login
def handle_login(request, role, template, redirect_url):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        if not email or not password:
            return render(request, template, {"error": "Both fields are required."})

        try:
            user = User.objects.get(email=email, role=role)
        except User.DoesNotExist:
            return render(request, template, {"error": "Invalid credentials."})

        if check_password(password, user.password):
            request.session.update({
                "user_id": user.id,
                "user_name": user.name,
                "user_role": user.role,
            })
            return redirect(redirect_url)

    return render(request, template)

# Login views for different roles
@never_cache_custom
@user
def login_customer(request):
    return handle_login(request, UserRole.CUSTOMER, "product_details/login.html", "home_view")

@never_cache_custom
@user
def login_seller(request):
    return handle_login(request, UserRole.SELLER_OWNER, "seller/login.html", "seller_dashboard")

@never_cache_custom
@user
def login_admin(request):
    return handle_login(request, UserRole.ADMIN, "admin/login.html", "admin_dashboard")

# Logout view
def logout(request):
    user_role = request.session.pop("user_role", None)
    request.session.flush()

    if user_role == UserRole.CUSTOMER:
        return redirect("home_view")
    elif user_role == UserRole.SELLER_OWNER:
        return redirect("login_seller")
    else:
        return redirect("login_admin")

# Home page view
@never_cache_custom
def home_view(request):
    user_role = request.session.get("user_role")
    if user_role == UserRole.SELLER_OWNER:
        return redirect("seller_dashboard")
    elif user_role == UserRole.CUSTOMER:
        products = Product.objects.all()
        return render(request, "product_details/index.html", {"products": products})
    return render(request, "product_details/index.html")

# Dashboard views
@never_cache_custom
def seller_dashboard(request):
    if request.session.get("user_role") != UserRole.SELLER_OWNER:
        return redirect("login_seller")
    return render(request, "seller/dashboard.html")


@never_cache_custom
def customer_dashboard(request):
    if request.session.get("user_role") != UserRole.CUSTOMER:
        return redirect("login")
    return render(request, "product_details/index.html")


@never_cache_custom
def admin_dashboard(request):
    return render(request, "admin/dashboard.html")

# Product-related views
@never_cache_custom
@user_login_required
def add_product(request):
    if request.method == "POST":
        product_name = request.POST.get("product_name")
        description = request.POST.get("description")
        price = request.POST.get("price")
        image = request.FILES.get("image")

        Product.objects.create(
            product_name=product_name,
            description=description,
            price=price,
            image=image,
        )
        return redirect("home_view")

    return render(request, "product_details/add_product.html")

# Shop view
@never_cache_custom
def shop_view(request):
    products = Product.objects.all()
    return render(request, "product_details/shop.html", {"products": products})

# Contact page view
@never_cache_custom
def contact(request):
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        email = request.POST.get("email", "").strip()
        message = request.POST.get("message", "").strip()

        if not (name and email and message):
            return render(request, "product_details/contact.html")

        Contact.objects.create(name=name, email=email, message=message)
        return redirect("home_view")

    return render(request, "product_details/contact.html")

# About page view
@never_cache_custom
def about_view(request):
    about = About.objects.first()
    return render(request, "product_details/about.html", {"about": about})

# Cart-related views
@never_cache_custom
@user_login_required
def get_cart(request):
    user_id = request.session.get("user_id")
    cart = Cart.objects.filter(user_id=user_id).first()

    if not cart:
        return redirect("shop_view")

    cart_items = cart.cart_items.all()
    total_price = sum(item.product.price * item.quantity for item in cart_items)

    return render(request, "product_details/cart.html", {
        "cart": cart, "cart_items": cart_items, "total_price": total_price,
    })

# Add to cart view
@never_cache_custom
@user_login_required
def add_to_cart(request):
    if request.method == "POST":
        user_id = request.session["user_id"]
        product_id = request.POST["product_id"]
        quantity = int(request.POST.get("quantity", 1))

        product = Product.objects.get(id=product_id)
        cart, _ = Cart.objects.get_or_create(user_id=user_id)

        cart_item, created = CartItem.objects.get_or_create(cart=cart, product=product)
        cart_item.quantity = F("quantity") + quantity if not created else quantity
        cart_item.save()

    return redirect("shop_view")

# Update cart view
@never_cache_custom
@user_login_required
def update_cart(request):
    if request.method == "POST":
        data = json.loads(request.body)
        item_id = data["item_id"]
        quantity = data["quantity"]

        cart_item = CartItem.objects.get(id=item_id)
        cart_item.quantity = quantity
        cart_item.save()

        cart = cart_item.cart
        total_price = sum(item.product.price * item.quantity for item in cart.cart_items.all())

        return JsonResponse(
            {"success": True, "item_total_price": cart_item.total_price(), "cart_total_price": total_price}
        )

    return HttpResponseNotAllowed(["POST"])

# Remove from cart view
@never_cache_custom
@user_login_required
def remove_cart(request):
    if request.method == "POST":
        item_id = request.POST.get("item_id")
        CartItem.objects.filter(id=item_id).delete()
    return redirect("cart_view")

# Checkout view
@never_cache_custom
@user_login_required
def checkout(request):
    """
    Handles the checkout process, including billing details.
    """
    user_id = request.session["user_id"]
    cart = Cart.objects.filter(user_id=user_id).first()

    if not cart:
        return redirect("shop_view")

    billing_address, _ = BillingAddress.objects.get_or_create(user_id=user_id)

    if request.method == "POST":
        fields = ["fullname", "street_address", "city", "state", "pin_code", "country", "contact_number"]
        for field in fields:
            setattr(billing_address, field, request.POST.get(field))
        billing_address.save()

        order = Order.objects.create(user_id=user_id, total_price=cart.total_price())
        OrderItem.objects.bulk_create([
            OrderItem(order=order, product=item.product, quantity=item.quantity)
            for item in cart.cart_items.all()
        ])

        cart.cart_items.all().delete()
        return redirect("payment_view", order_id=order.id)

    return render(request, "product_details/checkout.html", {
        "cart": cart, "billing_address": billing_address,
        "total_price": cart.total_price(),
    })

# Payment view
@never_cache_custom
@user_login_required
def payment_view(request, order_id):
    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        return redirect("home_view")

    if request.method == "POST":
        payment = Payment.objects.create(order=order, amount=order.total_price, status="Pending")
        order.status = "Processing"
        order.save()

        cart = Cart.objects.get(user=order.user)
        cart.cart_items.all().delete()

        return redirect("order_success", order_id=order.id)

    return render(request, "product_details/payment.html", {"order": order})

# Order success view
def order_success(request, order_id):
    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        return redirect("home_view")

    return render(request, "product_details/thankyou.html", {"order": order})


# # User Registration
# @never_cache_custom
# @user
# def register_customer(request):
#     return render(request, "product_details/register.html")

# # Seller Registration
# @never_cache_custom
# @user
# def register_seller(request):
#     return render(request, "seller/register.html")

# # Admin Registration
# @never_cache_custom
# @user
# def register_admin(request):
#     return render(request, "admin/register.html")

# # User Login
# @never_cache_custom
# @user
# def login_customer(request):
#     return render(request, "product_details/login.html")

# # Seller Login
# @never_cache_custom
# @user
# def login_seller(request):
#     if request.method == "POST":
#         email = request.POST.get("email")
#         password = request.POST.get("password")

#         if not email or not password:
#             return render(request, "seller/login.html")

#         try:
#             user = User.objects.get(email=email, role=UserRole.SELLER_OWNER)
#         except User.DoesNotExist:
#             return render(request, "seller/login.html")

#         if check_password(password, user.password):
#             request.session["user_id"] = user.id
#             request.session["user_name"] = user.name
#             request.session["user_role"] = user.role

#             return redirect("seller_dashboard")
#     return render(request, "seller/login.html")

# # Admin Login
# @never_cache_custom
# @user
# def login_admin(request):
#     if request.method == "POST":
#         email = request.POST.get("email")
#         password = request.POST.get("password")

#         if not email or not password:
#             return render(request, "admin/login.html")

#         try:
#             user = User.objects.get(email=email, role=UserRole.ADMIN)
#         except User.DoesNotExist:
#             return render(request, "admin/login.html")

#         if check_password(password, user.password):
#             request.session["user_id"] = user.id
#             request.session["user_name"] = user.name
#             request.session["user_role"] = user.role

#             return redirect("admin_dashboard")

#     return render(request, "admin/login.html")

# # User Logout
# def logout(request):
#     user_role = request.session.get("user_role")
#     request.session.flush()

#     if user_role == UserRole.CUSTOMER:
#         return redirect("home_view")

#     elif user_role == UserRole.SELLER_OWNER:
#         return redirect("login_seller")
#     else:
#         return redirect("login_admin")

# # Home Page
# @never_cache_custom
# def home_view(request):
#     products = Product.objects.all()
#     return render(request, "product_details/index.html", {"products": products})

# # Seller dashboard
# @never_cache_custom
# def seller_dashboard(request):
#     return render(request, "seller/dashboard.html")

# # Admin dashboard
# @never_cache_custom
# def admin_dashboard(request):
#     return render(request, "admin/dashboard.html")

# #Add Product
# @never_cache_custom
# @user_login_required
# def add_product(request):
#     if request.method == "POST":
#         product_name = request.POST.get("product_name")
#         description = request.POST.get("description")
#         price = request.POST.get("price")
#         image = request.FILES.get("image")

#         Product.objects.create(
#             product_name=product_name,
#             description=description,
#             price=price,
#             image=image,
#         )
#         return redirect("home_view")

#     return render(request, "product_details/add_product.html")

# # Shop View
# @never_cache_custom
# def shop_view(request):
#     products = Product.objects.all()
#     return render(request, "product_details/shop.html", {"products": products})

# # Contact Page
# @never_cache_custom
# def contact(request):
#     if request.method == "POST":
#         name = request.POST.get("name", "").strip()
#         email = request.POST.get("email", "").strip()
#         message = request.POST.get("message", "").strip()

#         if not (name and email and message):
#             return render(request, "product_details/contact.html")

#         Contact.objects.create(name=name, email=email, message=message)
#         return redirect("home_view")

#     return render(request, "product_details/contact.html")

# # About Page
# @never_cache_custom
# def about_view(request):
#     about = About.objects.first()
#     return render(request, "product_details/about.html", {"about": about})

# # View Cart
# @never_cache_custom
# @user_login_required
# def get_cart(request):
#     user_id = request.session.get("user_id")
#     if not user_id:
#         return redirect("login")

#     try:
#         user = User.objects.get(id=user_id)
#         cart = Cart.objects.get(user=user)
#     except (User.DoesNotExist, Cart.DoesNotExist):
#         return redirect("home_view")

#     cart_items = cart.cart_items.all()
#     total_price = sum(item.product.price * item.quantity for item in cart_items)

#     return render(
#         request,
#         "product_details/cart.html",
#         {
#             "cart": cart,
#             "cart_items": cart_items,
#             "total_price": total_price,
#         },
#     )

# # Add to Cart
# @never_cache_custom
# @user_login_required
# def add_to_cart(request):
#     if request.method == "POST":
#         user_id = request.session.get("user_id")
#         product_id = request.POST.get("product_id")
#         quantity = int(request.POST.get("quantity", 1))

#         quantity = int(quantity)
#         if quantity <= 0:
#             return redirect("shop_view")

#         user = User.objects.get(id=user_id)
#         product = Product.objects.get(id=product_id)
#         cart, _ = Cart.objects.get_or_create(user=user)

#         cart_item, created = CartItem.objects.get_or_create(
#             cart=cart, product=product
#             )
#         if created:
#             cart_item.quantity = quantity
#         else:
#             cart_item.quantity = F("quantity") + quantity
#         cart_item.save()

#     return redirect("shop_view")

# # Update Cart
# @never_cache_custom
# @user_login_required
# def update_cart(request):
#     if request.method == "POST":
#         data = json.loads(request.body)
#         item_id = data["item_id"]
#         quantity = data["quantity"]

#         cart_item = CartItem.objects.get(id=item_id)
#         cart_item.quantity = quantity
#         cart_item.save()

#         cart = cart_item.cart
#         total_price = sum(item.product.price * item.quantity for item in cart.cart_items.all())

#         return JsonResponse(
#             {"success": True, "item_total_price": cart_item.total_price(), "cart_total_price": total_price}
#         )

#     return HttpResponseNotAllowed(["POST"])

# # Remove from Cart
# @never_cache_custom
# @user_login_required
# def remove_cart(request):
#     if request.method == "POST":
#         item_id = request.POST.get("item_id")
#         CartItem.objects.filter(id=item_id).delete()

#     return redirect("cart_view")

# # Checkout
# @never_cache_custom
# @user_login_required
# def checkout(request):
#     user_id = request.session.get("user_id")

#     try:
#         user = User.objects.get(id=user_id)
#         cart = Cart.objects.get(user=user)
#     except (User.DoesNotExist, Cart.DoesNotExist):
#         return redirect("home_view")

#     billing_address, created = BillingAddress.objects.get_or_create(user=user)

#     if request.method == "POST":
#         billing_fields = [
#             "fullname", "street_address", "city", "state", "pin_code", "country", "contact_number"
#         ]
#         for field in billing_fields:
#             setattr(billing_address, field, request.POST.get(field))
#         billing_address.save()

#         order = Order.objects.create(user=user, total_price=cart.total_price())
#         for item in cart.cart_items.all():
#             OrderItem.objects.create(order=order, product=item.product, quantity=item.quantity)

#         return redirect("payment_view", order_id=order.id)

#     return render(
#         request,
#         "product_details/checkout.html",
#         {"cart": cart, "total_price": cart.total_price(), "billing_address": billing_address},
#     )

# # Payment View
# @never_cache_custom
# @user_login_required
# def payment_view(request, order_id):
#     try:
#         order = Order.objects.get(id=order_id)
#     except Order.DoesNotExist:
#         return redirect("home_view")

#     if request.method == "POST":
#         payment = Payment.objects.create(order=order, amount=order.total_price, status="Pending")
#         order.status = "Processing"
#         order.save()

#         cart = Cart.objects.get(user=order.user)
#         cart.cart_items.all().delete()

#         return redirect("order_success", order_id=order.id)

#     return render(request, "product_details/payment.html", {"order": order})

# # Order success view
# def order_success(request, order_id):
#     try:
#         order = Order.objects.get(id=order_id)
#     except Order.DoesNotExist:
#         return redirect("home_view")

#     return render(request, "product_details/thankyou.html", {"order": order})