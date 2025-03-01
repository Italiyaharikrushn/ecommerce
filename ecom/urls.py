from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from . import views

urlpatterns = [
    # Customer Authentication
    path("register/", views.register_customer, name="register"),
    path("login/", views.login_customer, name="login"),

    # Seller Authentication
    path("seller/register/", views.register_seller, name="register_seller"),
    path("seller/login/", views.login_seller, name="login_seller"),

    # Admin Authentication & Management
    path("admins/register/", views.register_admin, name="register_admin"),
    path("admins/login/", views.login_admin, name="login_admin"),
    path("admins/dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("admins/orders/", views.order, name="order"),
    path("admins/tablesdata/", views.table_data, name="table_data"),
    path("admins/tablesgeneral/", views.general_data, name="general_data"),
    path("user-chart/", views.user_chart, name="user-chart"),
    path("order-status-chart/", views.order_status_chart, name="order-status-chart"),
    path("order-chart/", views.order_chart, name="order-chart"),
    path("order-chart-page/", views.order_chart_page, name="order-chart-page"),

    # Logout
    path("logout/", views.logout, name="logout"),

    # General Pages
    path("", views.home_view, name="home_view"),
    path("about/", views.about_view, name="about_view"),
    path("contact/", views.contact, name="contact"),

    # Seller Dashboard & Product Management
    path("seller/dashboard/", views.seller_dashboard, name="seller_dashboard"),
    path("seller/add-product/", views.add_product, name="add_product"),
    path("seller/product-list/", views.product_list, name="product_list"),
    path("seller/orders/", views.view_orders, name="view_orders"),
    
    # Product Details & Management
    path("product/<int:product_id>/", views.product_detail, name="product_detail"),
    path("delete_product/<int:product_id>/", views.delete_product, name="delete_product"),
    path("update_product/<int:product_id>/", views.update_product, name="update_product"),
    path("shop/", views.shop_view, name="shop_view"),

    # Order Management (Seller & Customer)
    path("order/shipped/<int:item_id>/", views.mark_as_shipped, name="mark_as_shipped"),
    path("order-item/<int:item_id>/delivered/", views.mark_as_delivered, name="mark_as_delivered"),
    path("orders/cancel/<int:item_id>/", views.cancel_order_item, name="cancel_order_item"),
    path("order-success/<int:order_id>/", views.order_success, name="order_success"),
    path("orders/accept/<int:item_id>/", views.accept_order, name="accept_order"),
    path("customer/cancel-order/<int:order_id>/", views.customer_cancel_order, name="customer_cancel_order"),
    path('order/return/<int:item_id>/', views.return_order_item, name='return_order_item'),

    # Cart Management
    path("cart/", views.get_cart, name="cart_view"),
    path("cart/add/", views.add_to_cart, name="add_to_cart"),
    path("update-cart/", views.update_cart, name="update_cart"),
    path("cart/remove/", views.remove_cart, name="remove_cart"),

    # Checkout & Orders
    path("checkout/", views.checkout, name="checkout"),
    path("cart/my_orders/", views.my_orders_view, name="my_orders"),

    # Payment
    path("payment/<int:order_id>/", views.payment_view, name="payment_view"),

    # Invoice
    path("invoice/<int:order_id>/", views.generate_invoice, name="invoice_view"),
]

# Serving media files in development mode
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
