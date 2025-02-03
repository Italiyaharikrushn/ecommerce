from django.shortcuts import render, redirect
from .models import (Product, User, Contact, About, CartItem, Cart, Order, OrderItem, BillingAddress, Payment, UserRole, ShippingAddress, BankDetails )
from django.contrib.auth.hashers import make_password, check_password
from .utils import never_cache_custom, user, user_login_required
from django.http import JsonResponse, HttpResponseNotAllowed
import json
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.db.models import F
from django.core.mail import send_mail
from django.contrib import messages
from django.urls import reverse
from django.http import HttpResponseForbidden
from datetime import date, timedelta
from django.db import transaction

# Notify sellers about new order
def notify_sellers(order):
    seller_orders = {}
    for item in order.order_items.all():
        seller = item.product.seller
        if seller not in seller_orders:
            seller_orders[seller] = []
        seller_orders[seller].append(item)

    for seller, items in seller_orders.items():
        product_details = "\n".join([f"{item.quantity} x {item.product.product_name} (${item.total_price()})"for item in items])

        email_subject = f"New Order Notification - Order #{order.id}"
        email_body = f"Dear {seller.name},\n\nYou have a new order. Here are the details:\n\n{product_details}\n\nThank you."
        send_mail(subject=email_subject,message=email_body,from_email="no-reply@example.com",recipient_list=[seller.email],)

# Helper function to handle user registration
def register_user(request, role, template, redirect_url):
    if request.method == "POST":
        name = request.POST.get("name")
        email = request.POST.get("email")
        phone = request.POST.get("phone")
        password = request.POST.get("password")
        gender = request.POST.get("gender")

        if User.objects.filter(email=email, role=role).exists():
            context = {"name": name,"phone": phone,"gender": gender,"error": "Email already registered.",}
            return render(request, template, context)

        User.objects.create(name=name,email=email,phone=phone,password=make_password(password),gender=gender,role=role,)

        messages.success(request, "Registration successful! Please log in.")
        return redirect(redirect_url)

    return render(request, template)

# Views for user roles (Customer, Seller, Admin)
@never_cache_custom
@user
def register_customer(request):
    return register_user(request, UserRole.CUSTOMER, "product_details/register.html", "login")

@never_cache_custom
@user
def register_seller(request):
    if request.method == 'POST':
        try:
            with transaction.atomic():
                user = User.objects.create(
                    name=request.POST['name'],
                    email=request.POST['email'],
                    phone=request.POST['phone'],
                    password=make_password(request.POST['password']),
                    gender = request.POST.get("gender"),
                    role=UserRole.SELLER_OWNER
                )

                ShippingAddress.objects.create(
                    seller=user,
                    BusinessName=request.POST['business_name'],
                    BusinessAddress=request.POST['business_address'],
                    City=request.POST['city'],
                    state=request.POST['state'],
                    pincode=request.POST['pincode'],
                    country=request.POST['country']
                )

                BankDetails.objects.create(
                    seller=user,
                    BankAccountNo=request.POST['bank_account'],
                    IFSCCode=request.POST['ifsc'],
                    AccountHolderName=request.POST['account_holder_name']
                )

                messages.success(request, "Seller registration successful!")
                return redirect('seller_dashboard')

        except Exception as e:
            messages.error(request, f"Error during registration: {str(e)}")
            return render(request, 'seller/register.html')

    return render(request, 'seller/register.html')

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
            request.session.update({"user_id": user.id,"user_name": user.name,"user_role": user.role,})
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

    user_id = request.session.get("user_id")
    if not user_id:
        return redirect("login_seller")

    try:
        seller = User.objects.get(id=user_id, role=UserRole.SELLER_OWNER)
    except User.DoesNotExist:
        raise PermissionDenied("Seller not found.")

    seller_products = Product.objects.filter(seller_id=user_id)

    order_items = OrderItem.objects.filter(product__seller_id=user_id).select_related("order", "product")
    seller_orders = {}

    for item in order_items:
        order_id = item.order.id
        if order_id not in seller_orders:
            seller_orders[order_id] = {"order": item.order,"items": [],"total_price": 0,}

        seller_orders[order_id]["items"].append(item)
        seller_orders[order_id]["total_price"] += item.product.price * item.quantity

    return render(request,"seller/dashboard.html",{"name": seller.name,"products": seller_products,"orders": seller_orders.values(),},)

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
    if request.session.get("user_role") != UserRole.SELLER_OWNER:
        return redirect("login_seller")

    user_id = request.session.get("user_id")
    seller = User.objects.get(id=user_id, role=UserRole.SELLER_OWNER)

    try:
        user = User.objects.get(id=user_id)
        name = user.name
    except User.DoesNotExist:
        raise PermissionDenied("User not found.")

    if request.method == "POST":
        product_name = request.POST.get("product_name", "").strip()
        description = request.POST.get("description", "").strip()
        price = request.POST.get("price", "").strip()
        image = request.FILES.get("image")

        if not all([product_name, description, price, image]):
            return render(request,"seller/add_product.html",{"error": "All fields are required."},)

        try:
            price = float(price)
            if price < 0:
                raise ValueError("Price must be positive.")

            seller = User.objects.get(id=user_id, role=UserRole.SELLER_OWNER)

            Product.objects.create(product_name=product_name,description=description,price=price,image=image,seller=seller,)
            return redirect("product_list")

        except ValueError:
            return render(request,"seller/add_product.html",{"error": "Price must be a valid positive number.", "name": name},)

        except ObjectDoesNotExist:
            return render(request,"seller/add_product.html",{"error": "Seller account not found or unauthorized.", "name": name},)

        except Exception as e:
            return render(request,"seller/add_product.html",{"error": f"An unexpected error occurred: {e}", "name": name},)

    return render(request, "seller/add_product.html", {"name": name})

@never_cache_custom
@user_login_required
def product_list(request):
    user_role = request.session.get("user_role")
    user_id = request.session.get("user_id")
    products = Product.objects.filter(seller_id=user_id)

    if not user_id:
        raise PermissionDenied("You are not logged in.")

    try:
        user = User.objects.get(id=user_id)
        name = user.name
    except User.DoesNotExist:
        raise PermissionDenied("User not found.")

    if user_role == UserRole.SELLER_OWNER:
        products = Product.objects.filter(seller_id=user_id)
    elif user_role == UserRole.ADMIN:
        products = Product.objects.all()
    else:
        raise PermissionDenied("You do not have permission to view this page.")

    return render(request, "seller/product_list.html", {"products": products, "name": name})

def delete_product(request, product_id):
    if request.session.get("user_role") != UserRole.SELLER_OWNER:
        messages.error(request, "You do not have permission to perform this action.")
        return redirect("product_list")

    user_id = request.session.get("user_id")

    product = Product.objects.get(id=product_id)

    if product.seller_id != user_id:
        messages.error(request, "You do not have permission to delete this product.")
        return redirect("product_list")

    product.delete()
    messages.success(request, "Product deleted successfully.")
    return redirect(reverse("product_list"))

def update_product(request, product_id):
    if request.session.get("user_role") != UserRole.SELLER_OWNER:
        return HttpResponseForbidden("You do not have permission to perform this action.")

    user_id = request.session.get("user_id")
    product = Product.objects.get(id=product_id)

    if product.seller_id != user_id:
        raise PermissionDenied("You do not have permission to update this product.")

    try:
        user = User.objects.get(id=user_id)
        name = user.name
    except User.DoesNotExist:
        raise PermissionDenied("User not found.")

    if request.method == "POST":
        product_name = request.POST.get("product_name", "").strip()
        description = request.POST.get("description", "").strip()
        price = request.POST.get("price", "").strip()
        image = request.FILES.get("image")

        if not all([product_name, description, price]):
            return render(request,"seller/update_product.html",{"error": "All fields are required.", "product": product},)

        try:
            price = float(price)
            if price < 0:
                raise ValueError("Price must be positive.")

            product.product_name = product_name
            product.description = description
            product.price = price

            if image:
                product.image = image

            product.save()
            return redirect("product_list")

        except ValueError:
            return render(request,"seller/update_product.html",{"error": "Price must be a valid positive number.", "product": product},)

        except Exception as e:
            return render(request,"seller/update_product.html",{"error": f"An unexpected error occurred: {e}", "product": product},)

    return render(request, "seller/update_product.html", {"product": product, "name": name})

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

    return render(request,"product_details/cart.html",{"cart": cart,"cart_items": cart_items,"total_price": total_price,},)

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
            {"success": True,"item_total_price": cart_item.total_price(),"cart_total_price": total_price,})

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
    user_id = request.session.get("user_id")
    
    if not user_id:
        messages.error(request, "You need to be logged in to proceed.")
        return redirect("login")

    cart = Cart.objects.filter(user_id=user_id).first()

    if not cart or not cart.cart_items.exists():
        messages.error(request, "Your cart is empty.")
        return redirect("shop_view")

    billing_address, _ = BillingAddress.objects.get_or_create(user_id=user_id)

    if request.method == "POST":
        billing_fields = [
            "billing_fullname", "billing_address", "billing_city", "billing_state",
            "billing_pincode", "billing_country", "billing_contact_number",
            "shipping_fullname", "shipping_address", "shipping_city", "shipping_state",
            "shipping_pincode", "shipping_country", "shipping_contact_number"
        ]

        for field in billing_fields:
            setattr(billing_address, field, request.POST.get(field))
        
        billing_address.save()

        try:
            with transaction.atomic():
                order = Order.objects.create(user_id=user_id, total_price=cart.total_price())

                billing_address.order = order
                billing_address.save()

                dispatch_date = date.today() + timedelta(days=2)

                order_items = [
                    OrderItem(
                        order=order,
                        product=item.product,
                        quantity=item.quantity,
                        dispatch_date=dispatch_date,
                    ) for item in cart.cart_items.all()
                ]
                OrderItem.objects.bulk_create(order_items)

                notify_sellers(order)

                cart.cart_items.all().delete()

                messages.success(request, "Order placed successfully!")
                return redirect("payment_view", order_id=order.id)
        except Exception as e:
            messages.error(request, f"An error occurred during checkout: {e}")
            return redirect("checkout")

    return render(request, "product_details/checkout.html", {
        "cart": cart,
        "billing_address": billing_address,
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
        order = Order.objects.prefetch_related("order_items__product__seller").get(id=order_id)
    except Order.DoesNotExist:
        return redirect("home_view")

    return render(request,"product_details/thankyou.html",{"order": order, "seller": order.order_items.first().product.seller},)

def my_orders_view(request):
    user_role = request.session.get("user_role")
    user_id = request.session.get("user_id")

    user = User.objects.get(id=user_id)
    name = user.name

    if user_role == UserRole.CUSTOMER:
        orders = Order.objects.filter(user=user)
        return render(request, "product_details/my_orders.html", {"orders": orders, "name": name})

    else:
        raise PermissionDenied("You do not have permission to view this page.")

def view_orders(request):
    user_id = request.session.get("user_id")
    user_role = request.session.get("user_role")

    if user_role != UserRole.SELLER_OWNER:
        return redirect("login_seller")

    try:
        seller = User.objects.get(id=user_id, role=UserRole.SELLER_OWNER)
    except User.DoesNotExist:
        raise PermissionDenied("Seller not found.")

    order_items = OrderItem.objects.filter(product__seller_id=user_id).select_related("order", "product")

    orders_dict = {}
    today = date.today()
    two_days_from_today = today + timedelta(days=2)

    status_counts = {"onhold": 0,"pending": 0,"ready_to_ship": 0,}

    for item in order_items:
        order_id = item.order.id
        order_status = item.status.lower()

        if order_status in status_counts:
            status_counts[order_status] += 1

        if order_id not in orders_dict:
            orders_dict[order_id] = {"order": item.order,"items": [],"total_price": 0,}

        orders_dict[order_id]["items"].append(item)
        orders_dict[order_id]["total_price"] += item.product.price * item.quantity

        if item.dispatch_date:
            if today > item.dispatch_date:
                messages.error(request,f"Order item '{item.product.product_name}' has breached the dispatch date!",)
            elif two_days_from_today >= item.dispatch_date:
                messages.warning(request,f"Order item '{item.product.product_name}' is nearing the dispatch date!",)

    return render(request,"seller/order.html",{"name": seller.name,"orders": orders_dict.values(),"today": today,"two_days_from_today": two_days_from_today,"status_counts": status_counts,},)

def cancel_order_item(request, item_id):
    if request.method == "POST":
        user_id = request.session.get("user_id")
        if request.session.get("user_role") != UserRole.SELLER_OWNER:
            return redirect("login_seller")

        order_item = OrderItem.objects.get(id=item_id)

        if order_item.product.seller.id != user_id:
            raise PermissionDenied("You are not authorized to cancel this order item.")

        order = order_item.order
        order.total_price -= order_item.total_price()

        order_item.delete()

        order.save()

        if not order.order_items.exists():
            order.delete()

        return redirect("view_orders")

def accept_order(request, item_id):
    if request.method == "POST":
        user_id = request.session.get("user_id")

        if request.session.get("user_role") != UserRole.SELLER_OWNER:
            return redirect("login_seller")

        try:
            order_item = OrderItem.objects.select_related("product__seller").get(id=item_id)

            if order_item.product.seller.id != user_id:
                raise PermissionDenied("You are not authorized to accept this order item.")

            order_item.status = "ready_to_ship"
            order_item.save()

            order = order_item.order
            order.status = "Shipped"
            order.save()

        except OrderItem.DoesNotExist:
            raise PermissionDenied("Order item not found.")

        return redirect("view_orders")
