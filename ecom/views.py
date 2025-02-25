from .models import ( Product, User, Contact, About, CartItem, Cart, Order, OrderItem, BillingAddress, Payment, UserRole, ShippingAddress, BankDetails)
import json
from io import BytesIO
from datetime import date, datetime, timedelta
from django.shortcuts import render, redirect
from django.http import (JsonResponse, HttpResponse, HttpResponseForbidden, HttpResponseNotAllowed, HttpResponseRedirect)
from django.contrib import messages
from django.core.mail import send_mail
from django.template.loader import get_template
from django.urls import reverse
from django.db import transaction, IntegrityError
from django.db.models import Prefetch, Q, Count, F, Min
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.contrib.auth.hashers import make_password, check_password
from django.utils.timezone import now
from xhtml2pdf import pisa
from .utils import never_cache_custom, user_login_required

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

def register_user(request, role, template, redirect_url):
    if request.method == "POST":
        name = request.POST.get("name")
        email = request.POST.get("email")
        phone = request.POST.get("phone")
        password = request.POST.get("password")
        gender = request.POST.get("gender")
        country = request.POST.get("country")

        if User.objects.filter(email=email, role=role).exists():
            return render(request, template, {
                "name": name, "phone": phone, "gender": gender,  "country": country,
                "error": "Email already registered."
            })

        user = User( name=name, email=email, phone=phone, password=make_password(password), gender=gender, role=role, country=country )
        user.save()

        messages.success(request, "Registration successful! Please log in.")
        return redirect(redirect_url)
    return render(request, template)

@never_cache_custom
def register_customer(request):
    return register_user(request, UserRole.CUSTOMER, "product_details/register.html", "login")

@never_cache_custom
def register_seller(request):
    if request.method == 'POST':
        try:
            with transaction.atomic():
                email = request.POST['email']
                
                if User.objects.filter(email=email, role=UserRole.SELLER_OWNER).exists():
                    messages.error(request, "Email already registered as a seller.")
                    return render(request, 'seller/register.html', request.POST)

                user = User.objects.create(
                    name=request.POST['name'],
                    email=email,
                    phone=request.POST['phone'],
                    password=make_password(request.POST['password']),
                    gender=request.POST.get("gender"),
                    role=UserRole.SELLER_OWNER,
                    country=request.POST.get("country")
                )

                ShippingAddress.objects.create(
                    seller=user,
                    businessname=request.POST['business_name'],
                    businessaddress=request.POST['business_address'],
                    city=request.POST['city'],
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

        except IntegrityError:
            messages.error(request, "Seller already exists.")
        except Exception as e:
            messages.error(request, f"Error during registration: {str(e)}")

    return render(request, 'seller/register.html')

@never_cache_custom
def register_admin(request):
    return register_user(request, UserRole.ADMIN, "admins/register.html", "login_admin")

def handle_login(request, role, template, redirect_url):
    if request.session.get("user_id"):
        return redirect(redirect_url)

    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        if not email or not password:
            messages.error(request, "Both email and password are required.")
            return render(request, template)

        try:
            user = User.objects.get(email=email, role=role)
        except User.DoesNotExist:
            messages.error(request, "Invalid email or password.")
            return render(request, template)

        if check_password(password, user.password):
            request.session.update({ "user_id": user.id, "user_name": user.name, "user_role": user.role, })
            return redirect(redirect_url)

        messages.error(request, "Incorrect password.")
    
    return render(request, template)

# @user_login_required
@never_cache_custom
def login_customer(request):
    return handle_login(request, UserRole.CUSTOMER, "product_details/login.html", "home_view")

# @user_login_required
@never_cache_custom
def login_seller(request):
    return handle_login(request, UserRole.SELLER_OWNER, "seller/login.html", "seller_dashboard")

# @user_login_required
@never_cache_custom
def login_admin(request):
    return handle_login(request, UserRole.ADMIN, "admins/login.html", "admin_dashboard")

# Function to log out users and redirect them to the appropriate page
def logout(request):
    user_role = request.session.pop("user_role", None)
    request.session.flush()

    if user_role == UserRole.CUSTOMER:
        return redirect("home_view")
    elif user_role == UserRole.SELLER_OWNER:
        return redirect("login_seller")
    elif user_role == UserRole.ADMIN:
        return redirect("login_admin")

    return redirect("home_view")

# Function to display the home page based on user role
@never_cache_custom
def home_view(request):
    user_role = request.session.get("user_role")

    if user_role == UserRole.SELLER_OWNER:
        return redirect("seller_dashboard")
    elif user_role == UserRole.CUSTOMER:
        products = Product.objects.all()
        return render(request, "product_details/index.html", {"products": products})
    elif user_role == UserRole.ADMIN:
        return redirect("admin_dashboard")
    return render(request, "product_details/index.html")

# Function to display the seller's dashboard with their products and orders
@never_cache_custom
@user_login_required(allowed_roles=["seller_owner"])
def seller_dashboard(request):
    user_id = request.session.get("user_id")

    try:
        seller = User.objects.get(id=user_id, role="seller_owner")
    except User.DoesNotExist:
        raise PermissionDenied("Seller not found.")

    seller_products = Product.objects.filter(seller_id=user_id)
    order_items = OrderItem.objects.filter(product__seller_id=user_id).select_related("order", "product")

    seller_orders = {}
    for item in order_items:
        order_id = item.order.id
        if order_id not in seller_orders:
            seller_orders[order_id] = {"order": item.order, "items": [], "total_price": 0}
        
        seller_orders[order_id]["items"].append(item)
        seller_orders[order_id]["total_price"] += item.product.price * item.quantity

    return render(request, "seller/dashboard.html", {"name": seller.name, "products": seller_products, "orders": seller_orders.values()})

# Function to display the customer dashboard
@never_cache_custom
@user_login_required(allowed_roles=["ROLE_CUSTOMER"])
def customer_dashboard(request):
    return render(request, "product_details/index.html")

# Function to display the admin dashboard with order statistics
@never_cache_custom
@user_login_required(allowed_roles=["ROLE_ADMIN"])
def admin_dashboard(request):
    today = datetime.today().date()
    customer_orders = OrderItem.objects.filter(order_date=today)
    total_orders = Order.objects.count()
    today_orders = OrderItem.objects.filter(order_date=today).count()
    completed_orders = Order.objects.filter(status="Delivered").count()

    context = { "total_orders": total_orders, "today_orders": today_orders, "completed_orders": completed_orders, "customer_orders": customer_orders }
    
    return render(request, "admins/dashboard.html", context)

# Function to add a new product by a seller
@never_cache_custom
def add_product(request):
    if request.session.get("user_role") != UserRole.SELLER_OWNER:
        return redirect("login_seller")

    user_id = request.session.get("user_id")

    try:
        seller = User.objects.get(id=user_id, role=UserRole.SELLER_OWNER)
        name = seller.name
    except User.DoesNotExist:
        raise PermissionDenied("User not found.")

    if request.method == "POST":
        product_name = request.POST.get("product_name", "").strip()
        description = request.POST.get("description", "").strip()
        price = request.POST.get("price", "").strip()
        total_quantity = request.POST.get("total_quantity", "").strip()
        image = request.FILES.get("image")

        if not all([product_name, description, price, total_quantity, image]):
            return render(request, "seller/add_product.html", {
                "error": "All fields are required.",
                "name": name
            })

        try:
            price = float(price)
            total_quantity = int(total_quantity)

            if price < 0:
                raise ValueError("Price must be positive.")
            if total_quantity < 0:
                raise ValueError("Total quantity must be positive.")

            Product.objects.create(product_name=product_name,description=description,price=price,total_quantity=total_quantity,image=image,seller=seller,)
            return redirect("product_list")

        except ValueError as e:
            return render(request, "seller/add_product.html", {
                "error": str(e),
                "name": name
            })

        except ObjectDoesNotExist:
            return render(request, "seller/add_product.html", {
                "error": "Seller account not found or unauthorized.",
                "name": name
            })

        except Exception as e:
            return render(request, "seller/add_product.html", {
                "error": f"An unexpected error occurred: {e}",
                "name": name
            })

    return render(request, "seller/add_product.html", {"name": name})

# Function to display product details
@never_cache_custom
def product_detail(request, product_id):
    product = Product.objects.get(id=product_id)
    return render(request, 'seller/product_detail.html', {'product': product})

# Function to display the list of products based on user role
@never_cache_custom
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

# Function to delete a product by a seller
@never_cache_custom
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

# Function to update product details
@never_cache_custom
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

# Function to display the shop view
@never_cache_custom
def shop_view(request):
    products = Product.objects.all()
    return render(request, "product_details/shop.html", {"products": products})

# Contact Form Submission
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

# About Page View
@never_cache_custom
def about_view(request):
    about = About.objects.first()
    return render(request, "product_details/about.html", {"about": about})

# Retrieve Cart Details
@never_cache_custom
def get_cart(request):
    user_id = request.session.get("user_id")
    cart = Cart.objects.filter(user_id=user_id).first()

    if not cart:
        return redirect("shop_view")

    cart_items = cart.cart_items.all()
    total_price = sum(item.product.price * item.quantity for item in cart_items)

    return render(request,"product_details/cart.html",{"cart": cart,"cart_items": cart_items,"total_price": total_price,},)

# Add Product to Cart
@never_cache_custom
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

# Update Cart Item Quantity
@never_cache_custom
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

# Remove Item from Cart
@never_cache_custom
def remove_cart(request):
    if request.method == "POST":
        item_id = request.POST.get("item_id")
        CartItem.objects.filter(id=item_id).delete()
    return redirect("cart_view")

# Checkout Process
@never_cache_custom
def checkout(request):
    user_id = request.session.get("user_id")
    cart = Cart.objects.filter(user_id=user_id).first()

    if not cart or not cart.cart_items.exists():
        messages.error(request, "Your cart is empty.")
        return redirect("shop_view")

    billing_address, _ = BillingAddress.objects.get_or_create(user_id=user_id)

    if request.method == "POST":
        billing_fields = [
            "billing_fullname", "billing_address", "billing_city", "billing_state", "billing_pincode", "billing_country", "billing_contact_number",
            "shipping_fullname", "shipping_address", "shipping_city", "shipping_state", "shipping_pincode", "shipping_country", "shipping_contact_number"
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
                delivery_date = dispatch_date + timedelta(days=5)

                order_items = [
                    OrderItem( order=order, product=item.product, quantity=item.quantity, dispatch_date=dispatch_date, delivery_date=delivery_date, ) for item in cart.cart_items.all()
                ]
                OrderItem.objects.bulk_create(order_items)

                notify_sellers(order)

                cart.cart_items.all().delete()

                messages.success(request, "Order placed successfully!")
                return redirect("payment_view", order_id=order.id)
        except Exception as e:
            messages.error(request, f"An error occurred during checkout: {e}")
            return redirect("checkout")

    return render(request, "product_details/checkout.html", { "cart": cart, "billing_address": billing_address, "total_price": cart.total_price(), })

# Handles payment processing for an order
@never_cache_custom
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

# Displays order success page after payment completion
@never_cache_custom
def order_success(request, order_id):
    try:
        order = Order.objects.prefetch_related("order_items__product__seller").get(id=order_id)
    except Order.DoesNotExist:
        return redirect("home_view")

    return render(request,"product_details/thankyou.html",{"order": order, "seller": order.order_items.first().product.seller},)

# Retrieves and displays all orders for the seller
@never_cache_custom
def seller_orders(request):
    orders = Order.objects.all()
    return render(request, 'seller/order.html', {'orders': orders})

# Retrieves and displays orders for the logged-in user based on their role (customer or seller)
@never_cache_custom
def my_orders_view(request):
    user_role = request.session.get("user_role")
    user_id = request.session.get("user_id")

    user = User.objects.get(id=user_id)
    name = user.name

    if user_role == UserRole.CUSTOMER:
        orders = Order.objects.filter(user=user).prefetch_related(
            Prefetch("order_items", queryset=OrderItem.objects.filter(~Q(status="Canceled")).select_related("product__seller"))
        )

        seller_orders = {}

        for order in orders:
            seller_items = {}
            for item in order.order_items.all():
                seller = item.product.seller

                if seller not in seller_orders:
                    seller_orders[seller] = []

                if order.id not in seller_items:
                    seller_items[order.id] = { "order": order, "items": [], "total_price": 0, }

                seller_items[order.id]["items"].append(item)
                seller_items[order.id]["total_price"] += item.product.price * item.quantity

            if seller_items:
                seller_orders[seller].extend(seller_items.values())

        return render(request, "product_details/my_orders.html", {"seller_orders": seller_orders, "name": name})

    elif user_role == UserRole.SELLER:
        orders = OrderItem.objects.filter(product__seller=user).exclude(status="Canceled").select_related("order", "product")

        seller_orders = {}
        for item in orders:
            order_id = item.order.id
            if order_id not in seller_orders:
                seller_orders[order_id] = { "order": item.order, "items": [], "total_price": 0, }

            seller_orders[order_id]["items"].append(item)
            seller_orders[order_id]["total_price"] += item.product.price * item.quantity

        return render(request, "product_details/seller_orders.html", {"orders": seller_orders.values(), "name": name})

    else:
        raise PermissionDenied("You do not have permission to view this page.")

# Retrieves and manages order-related data for a seller owner
@never_cache_custom
def view_orders(request):
    today = date.today()
    two_days_from_today = today + timedelta(days=2)

    user_id = request.session.get("user_id")
    user_role = request.session.get("user_role")

    if user_role != UserRole.SELLER_OWNER:
        return redirect("login_seller")

    seller = User.objects.get(id=user_id, role=UserRole.SELLER_OWNER)

    OrderItem.objects.filter(status="shipped", delivery_date=today).update(status="delivered")

    order_items = OrderItem.objects.filter(product__seller_id=user_id).select_related("order", "product")
    statuses = list(OrderItem.objects.filter(product__seller_id=user_id).values("status").annotate(count=Count("status")))
    
    all_statuses = {"onhold": 0, "pending": 0, "ready_to_ship": 0, "shipped": 0, "return_requested": 0, "returned": 0}
    for status in statuses:
        all_statuses[status["status"].lower()] = status["count"]

    orders_dict = {}
    for item in order_items:
        order_id = item.order.id

        if order_id not in orders_dict:
            orders_dict[order_id] = {"order": item.order, "items": [], "total_price": 0, "order_date": None}

        orders_dict[order_id]["items"].append(item)
        orders_dict[order_id]["total_price"] += item.product.price * item.quantity

    order_dates = OrderItem.objects.filter(order_id__in=orders_dict.keys()).values("order_id").annotate(order_date=Min("order_date"))
    for entry in order_dates:
        if entry["order_id"] in orders_dict:
            orders_dict[entry["order_id"]]["order_date"] = entry["order_date"]

    for item in order_items:
        if item.dispatch_date:
            if today > item.dispatch_date:
                messages.error(request, f"Order item '{item.product.product_name}' has breached the dispatch date!")
            elif two_days_from_today >= item.dispatch_date:
                messages.warning(request, f"Order item '{item.product.product_name}' is nearing the dispatch date!")

    return render(request, "seller/order.html",{"name": seller.name,"orders": orders_dict.values(),"today": today,"two_days_from_today": two_days_from_today,"status_counts": all_statuses,})

# Marks an order item as shipped if its status is 'ready_to_ship'.
def mark_as_shipped(request, item_id):
    order_item = OrderItem.objects.get(id=item_id)

    if order_item.status == "ready_to_ship":
        order_item.status = "shipped"
        order_item.dispatch_date = now().date()
        order_item.save()

        order = order_item.order
        if all(item.status == "shipped" for item in order.order_items.all()):
            order.status = "Shipped"
            order.save()

        messages.success(request, f"Order item '{order_item.product.product_name}' has been marked as shipped.")
    else:
        messages.warning(request, "This order item cannot be shipped.")

    return HttpResponseRedirect(request.META.get("HTTP_REFERER", "/"))

# Marks an order item as delivered if its status is 'shipped'.
def mark_as_delivered(request, item_id):
    order_item = OrderItem.objects.get(id=item_id)

    if order_item.status == "shipped":
        old_status = order_item.status
        order_item.status = "delivered"
        order_item.delivery_date = now().date()
        order_item.save()

        order_item.update_product_quantity(old_status, order_item.status)

        messages.success(request, f"Order item '{order_item.product.product_name}' has been marked as delivered. Stock updated.")

        order = order_item.order
        if all(item.status == "delivered" for item in order.order_items.all()):
            order.status = "Delivered"
            order.save()
    else:
        messages.warning(request, "This order item cannot be marked as delivered.")

    return HttpResponseRedirect(request.META.get("HTTP_REFERER", "/"))

# Updates order items with status 'shipped' to 'delivered' if their delivery date is today.
@transaction.atomic
def update_order_status(request, order_id):
    if request.method != "POST":
        messages.error(request, "Invalid request method.")
        return redirect("view_orders")

    user_role = request.session.get("user_role")
    order = Order.objects.get(id=order_id)

    if user_role not in [UserRole.SELLER_OWNER, UserRole.ADMIN]:
        raise PermissionDenied("You do not have permission to update order status.")

    new_status = request.POST.get("status")

    if new_status not in dict(Order.ORDER_STATUS_CHOICES):
        messages.error(request, "Invalid order status.")
        return redirect("view_orders")

    try:
        with transaction.atomic():
            for item in order.order_items.all():
                item.status = new_status
                item.save()

            order.status = new_status
            order.calculate_total_price()
            order.save()

            messages.success(request, f"Order #{order.id} status updated to {new_status}.")
    except Exception as e:
        messages.error(request, f"An error occurred while updating the order: {str(e)}")

    return redirect("view_orders")

# Marks an order item as 'Returned' if its status is 'Delivered'.
def return_order_item(request, item_id):
    order_item = OrderItem.objects.get(id=item_id)

    if order_item.status == "Delivered":
        order_item.status = "Returned"
        order_item.save()
        messages.success(request, f"Order item '{order_item.product.product_name}' has been marked as Returned.")
    else:
        messages.warning(request, "This order item cannot be returned.")

    return HttpResponseRedirect(request.META.get("HTTP_REFERER", "/"))

# Handles order item cancellation by customer, seller, or admin.
def cancel_order_item(request, item_id):
    if request.method != "POST":
        messages.error(request, "Invalid request method.")
        return redirect("view_orders")

    user_id = request.session.get("user_id")
    user_role = request.session.get("user_role")
    order_item = OrderItem.objects.get(id=item_id)
    order = order_item.order

    if user_role == UserRole.CUSTOMER and order.user.id != user_id:
        raise PermissionDenied("You are not authorized to cancel this order.")
    elif user_role == UserRole.SELLER_OWNER and order_item.product.seller.id != user_id:
        raise PermissionDenied("You are not authorized to cancel this order item.")
    elif user_role not in [UserRole.CUSTOMER, UserRole.SELLER_OWNER, UserRole.ADMIN]:
        raise PermissionDenied("You do not have permission to cancel orders.")

    try:
        with transaction.atomic():
            order.total_price -= order_item.total_price()
            order.total_price = max(order.total_price, 0)

            order_item.status = "cancelled"
            order_item.save()

            remaining_items = order.order_items.exclude(status="cancelled")
            statuses = {item.status for item in remaining_items}
            
            if statuses == {"ready_to_ship"}:
                order.status = "Processing"
            elif statuses == {"pending"}:
                order.status = "Pending"
            else:
                order.status = "Partially Processed"
            
            if not remaining_items.exists():
                order.status = "Cancelled"

            order.save()
            messages.success(request, f"Order item '{order_item.product.product_name}' has been cancelled.")
    except Exception as e:
        messages.error(request, f"An error occurred while cancelling the order item: {str(e)}")

    return redirect("view_orders")

# Allows a customer to cancel their order if it's not already completed or cancelled.
def customer_cancel_order(request, order_id):
    if request.method == "POST":
        user_id = request.session.get("user_id")

        order = Order.objects.get(id=order_id, user_id=user_id)

        if order.status in ["Cancelled", "Completed"]:
            raise PermissionDenied("You cannot cancel this order.")

        order.order_items.update(status="cancelled")

        order.status = "Cancelled"
        order.save()

        return redirect("my_orders")

# Allows a seller to accept an order item and update its status to 'ready_to_ship'.
def accept_order(request, item_id):
    if request.method == "POST":
        user_id = request.session.get("user_id")

        if request.session.get("user_role") != UserRole.SELLER_OWNER:
            return redirect("login_seller")

        try:
            order_item = OrderItem.objects.select_related("product__seller", "order").get(id=item_id)

            if order_item.product.seller.id != user_id:
                raise PermissionDenied("You are not authorized to accept this order item.")
            
            order_item.status = "ready_to_ship"  
            order_item.save()

            order = order_item.order
            all_order_items = order.order_items.all()

            item_statuses = {item.status.lower() for item in all_order_items}
            if "pending" in item_statuses:
                order.status = "Pending"
            elif all(status == "ready_to_ship" for status in item_statuses):
                order.status = "Processing"
            elif all(status == "shipped" for status in item_statuses):
                order.status = "Shipped"
            elif all(status == "completed" for status in item_statuses):
                order.status = "Completed"
            order.save()

        except OrderItem.DoesNotExist:
            raise PermissionDenied("Order item not found.")

        return redirect("view_orders")

# Generates a PDF invoice for a given order.
def generate_invoice(request, order_id):
    try:
        order = Order.objects.get(id=order_id)
        
        if order.order_items.exists():
            seller = order.order_items.first().product.seller
            seller_address = ShippingAddress.objects.filter(seller=seller).first()
        else:
            seller_address = None
        
        if not hasattr(order, 'billing_address') or order.billing_address is None:
            existing_billing_address = BillingAddress.objects.filter(user=order.user).first()
            if existing_billing_address:
                billing_address = existing_billing_address

        else:
            billing_address = order.billing_address
        
        template_path = 'seller/label.html'
        context = { 'order': order, 'billing_address': billing_address, 'seller_address': seller_address }
        
        template = get_template(template_path)
        html = template.render(context)
        
        response = BytesIO()
        pdf = pisa.pisaDocument(BytesIO(html.encode("UTF-8")), response)
        
        if not pdf.err:
            return HttpResponse(response.getvalue(), content_type='application/pdf')
        return HttpResponse('Error generating PDF', status=500)

    except Order.DoesNotExist:
        return HttpResponse('Order not found', status=404)

# Fetches all users except admins and renders the user data table.
def table_data(request):
    users = User.objects.exclude(role="ROLE_ADMIN")
    context = {
        "users": users,
    }
    return render(request, "admins/tables-data.html", context)

# Retrieves all products and renders the product data table.
def general_data(request):
    products = Product.objects.all()
    context = {
        "products": products,
    }
    return render(request, "admins/tables-general.html", context)

# Fetches all orders and renders the order management page.
def order(request):
    orders = Order.objects.all()
    context = {
        "orders" : orders,
    }
    return render(request, "admins/orders.html", context)

# Fetches recent orders placed by the logged-in user and renders the sales page.
def recent_sales(request):
    customer_orders = OrderItem.objects.filter(order__user=request.user).select_related("product", "order")

    context = {
        "customer_orders": customer_orders
    }
    return render(request, "recent_sales.html", context)

# Generates user distribution data by role and country for a chart.
def user_chart(request):
    countries = User.objects.values_list("country", flat=True).distinct()
    
    user_counts = (
        User.objects.values("country", "role")
        .annotate(count=Count("id"))
    )

    data = { "roles": ["Customer", "Seller"], "countries": list(countries), "customers": [], "sellers": [] }

    country_stats = {country: {"customers": 0, "sellers": 0} for country in countries}

    for entry in user_counts:
        country = entry["country"]
        role = entry["role"]
        count = entry["count"]

        if role == "ROLE_CUSTOMER":
            country_stats[country]["customers"] = count
        elif role == "seller_owner":
            country_stats[country]["sellers"] = count

    data["customers"] = [country_stats[c]["customers"] for c in countries]
    data["sellers"] = [country_stats[c]["sellers"] for c in countries]

    return JsonResponse(data)

# Generates order status distribution data for a chart.
def order_status_chart(request):
    status_counts = OrderItem.objects.values("status").annotate(count=Count("id"))

    data = {entry["status"]: entry["count"] for entry in status_counts}

    return JsonResponse(data)

# Generates order count data for the last 30 days for a chart.
def order_chart(request):
    today = datetime.today().date()
    last_30_days = [today - timedelta(days=i) for i in range(29, -1, -1)]

    user_id = request.session.get("user_id")

    data = OrderItem.objects.filter(order_date__gte=today - timedelta(days=30), product__seller_id=user_id) \
                            .values("order_date") \
                            .annotate(order_count=Count("id")) \
                            .order_by("order_date")

    order_data = {item["order_date"]: item["order_count"] for item in data}

    labels = [date.strftime("%d %b %Y") for date in last_30_days]
    values = [order_data.get(date, 0) for date in last_30_days]

    return JsonResponse({"labels": labels, "values": values})

# Renders the dashboard page for the seller with order statistics.
def order_chart_page(request):
    return render(request, "seller/dashboard.html")
