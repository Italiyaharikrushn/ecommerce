from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # User Authentication
    path("register/", views.register_customer, name="register"),
    path("login/", views.login_customer, name="login"),

    # User Authentication - Seller
    path("seller/register/", views.register_seller, name="register_seller"),
    path("seller/login/", views.login_seller, name="login_seller"),

    # Admin Authentication
    path("admin/register/", views.register_admin, name="register_admin"),
    path("admin/login/", views.login_admin, name="login_admin"),

    # logout
    path("logout/", views.logout, name="logout"),

    # Home and About
    path("", views.home_view, name="home_view"),
    path("seller/dashboard/", views.seller_dashboard, name="seller_dashboard"),
    path("admin/dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("about/", views.about_view, name="about_view"),

    # Products
    path('add-product/', views.add_product, name='add_product'),
    path('product-list/', views.product_list, name='product_list'),
    path("shop/", views.shop_view, name="shop_view"),

    # Contact
    path("contact/", views.contact, name="contact"),

    # Cart
    path("cart/", views.get_cart, name="cart_view"),
    path("cart/add/", views.add_to_cart, name="add_to_cart"),
    path("update-cart/", views.update_cart, name="update_cart"),
    path("cart/remove/", views.remove_cart, name="remove_cart"),

    # Checkout
    path("checkout/", views.checkout, name="checkout"),

    # Payment
    path("payment/<int:order_id>/", views.payment_view, name="payment_view"),

    # Order
    path("order-success/<int:order_id>/", views.order_success, name="order_success"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
