from django.shortcuts import render, redirect
from .models import Product, User, Contact, About, CartItem, Cart, Order, OrderItem, BillingAddress, Payment, UserRole
from django.contrib import messages
from django.contrib.auth.hashers import make_password, check_password
from .utils import never_cache_custom, user, user_login_required
from django.http import JsonResponse, HttpResponseNotAllowed
import json
from django.db.models import F

# User Registration
@never_cache_custom
@user
def register(request):
    if request.method == "POST":
        name = request.POST.get("name")
        email = request.POST.get("email")
        phone = request.POST.get("phone")
        password = request.POST.get("password")
        gender = request.POST.get("gender")
        age = request.POST.get("age")
        role = request.POST.get("role")

        if role not in [UserRole.CUSTOMER, UserRole.SELLER_OWNER, UserRole.ADMIN]:
            messages.error(request, "Invalid role selected.")
            return redirect("register")

        if User.objects.filter(email=email).exists():
            messages.error(request, "Email is already registered.")
            return render(
                request,
                "product_details/register.html",
                {
                    "name": name,
                    "phone": phone,
                    "gender": gender,
                    "age": age,
                    "role": role,
                },
            )

        hashed_password = make_password(password)

        user = User(
            name=name,
            email=email,
            phone=phone,
            password=hashed_password,
            gender=gender,
            age=age,
            role=role
        )
        user.save()

        messages.success(request, "Registration successful! Please log in.")

        return redirect("login")

    return render(request, "product_details/register.html")

# User Login
@never_cache_custom
@user
def login(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        if not email or not password:
            messages.error(request, "Both email and password are required.")
            return render(request, "product_details/login.html")

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            messages.error(request, "User not found.")
            return render(request, "product_details/login.html")

        if check_password(password, user.password):
            request.session["user_id"] = user.id
            request.session["user_name"] = user.name
            request.session["user_role"] = user.role
            
            if user.role == UserRole.CUSTOMER:
                messages.success(request, f"Welcome, {user.name}!")
                return redirect("home_view")
            elif user.role == UserRole.SELLER_OWNER:
                messages.success(request, f"Welcome, {user.name} (Seller Owner)!")
                return redirect("seller_dashboard")
            elif user.role == UserRole.ADMIN:
                messages.success(request, f"Welcome, {user.name} (Admin)!")
                return redirect("admin_dashboard")

        messages.error(request, "Invalid email or password.")
    return render(request, "product_details/login.html")

# User Logout
def logout(request):
    user_role = request.session.get("user_role")
    request.session.flush()
    messages.success(request, "You have been logged out successfully.")

    if user_role == UserRole.CUSTOMER:
        return redirect("home_view")
    
    else:
        return redirect("login")

# Home Page
@never_cache_custom
def home_view(request):
    products = Product.objects.all()
    return render(request, "product_details/index.html", {"products": products})

@never_cache_custom
def seller_dashboard(request):
    return render(request, "seller/dashboard.html")
    # products = Product.objects.all()
    # return render(request, "product_details/index.html", {"products": products})

@never_cache_custom
def admin_dashboard(request):
    return render(request, "admin/dashboard.html")
    # products = Product.objects.all()
    # return render(request, "product_details/index.html", {"products": products})

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
        messages.success(request, "Product added successfully!")
        return redirect("home_view")

    return render(request, "product_details/add_product.html")

# Shop View
@never_cache_custom
def shop_view(request):
    products = Product.objects.all()
    return render(request, "product_details/shop.html", {"products": products})

# Contact Page
@never_cache_custom
def contact(request):
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        email = request.POST.get("email", "").strip()
        message = request.POST.get("message", "").strip()

        if not (name and email and message):
            messages.error(request, "All fields are required.")
            return render(request, "product_details/contact.html")

        Contact.objects.create(name=name, email=email, message=message)
        messages.success(request, "Thank you for reaching out!")
        return redirect("home_view")

    return render(request, "product_details/contact.html")

# About Page
@never_cache_custom
def about_view(request):
    about = About.objects.first()
    return render(request, "product_details/about.html", {"about": about})

# View Cart
@never_cache_custom
@user_login_required
def get_cart(request):
    user_id = request.session.get("user_id")
    if not user_id:
        return redirect("login")

    try:
        user = User.objects.get(id=user_id)
        cart = Cart.objects.get(user=user)
    except (User.DoesNotExist, Cart.DoesNotExist):
        return redirect("home_view")

    cart_items = cart.cart_items.all()
    total_price = sum(item.product.price * item.quantity for item in cart_items)

    return render(
        request,
        "product_details/cart.html",
        {
            "cart": cart,
            "cart_items": cart_items,
            "total_price": total_price,
        },
    )

# Add to Cart
@never_cache_custom
@user_login_required
def add_to_cart(request):
    if request.method == "POST":
        user_id = request.session.get("user_id")
        product_id = request.POST.get("product_id")
        quantity = int(request.POST.get("quantity", 1))

        try:
            quantity = int(quantity)
            if quantity <= 0:
                messages.error(request, "Invalid quantity specified.")
                return redirect("shop_view")

            user = User.objects.get(id=user_id)
            product = Product.objects.get(id=product_id)
            cart, _ = Cart.objects.get_or_create(user=user)

            cart_item, created = CartItem.objects.get_or_create(
                cart=cart, product=product
            )
            if created:
                cart_item.quantity = quantity
            else:
                cart_item.quantity = F("quantity") + quantity
            cart_item.save()

            messages.success(request, f"{product.product_name} added to cart.")
        except (User.DoesNotExist, Product.DoesNotExist):
            messages.error(request, "Error adding product to cart.")

    return redirect("shop_view")

# Update Cart
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

# Remove from Cart
@never_cache_custom
@user_login_required
def remove_cart(request):
    if request.method == "POST":
        item_id = request.POST.get("item_id")
        CartItem.objects.filter(id=item_id).delete()
        messages.success(request, "Item removed from cart.")

    return redirect("cart_view")

# Checkout
@never_cache_custom
@user_login_required
def checkout(request):
    user_id = request.session.get("user_id")

    try:
        user = User.objects.get(id=user_id)
        cart = Cart.objects.get(user=user)
    except (User.DoesNotExist, Cart.DoesNotExist):
        return redirect("home_view")

    billing_address, created = BillingAddress.objects.get_or_create(user=user)

    if request.method == "POST":
        billing_fields = [
            "fullname", "street_address", "city", "state", "pin_code", "country", "contact_number"
        ]
        for field in billing_fields:
            setattr(billing_address, field, request.POST.get(field))
        billing_address.save()

        order = Order.objects.create(user=user, total_price=cart.total_price())
        for item in cart.cart_items.all():
            OrderItem.objects.create(order=order, product=item.product, quantity=item.quantity)

        return redirect("payment_view", order_id=order.id)

    return render(
        request,
        "product_details/checkout.html",
        {"cart": cart, "total_price": cart.total_price(), "billing_address": billing_address},
    )

# Payment View
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
