import uuid
from django.db import models
from django.core.validators import MinValueValidator
from django.core.validators import MinLengthValidator
from django.utils.timezone import now

def get_image_upload_to(instance, filename):
    ext = filename.split(".")[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return f"profile_images/{filename}"

class UserRole(models.TextChoices):
    CUSTOMER = 'ROLE_CUSTOMER', 'Customer'
    SELLER_OWNER = 'seller_owner', 'Seller Owner'
    ADMIN = 'ROLE_ADMIN', 'Admin'

class User(models.Model):
    GENDER_CHOICES = [
        ("Male", "Male"),
        ("Female", "Female"),
        ("Other", "Other"),
    ]

    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=14)
    password = models.CharField(max_length=255)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, default="Other")
    role = models.CharField(max_length=21, choices=UserRole.choices)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.phone.startswith("+91-"):
            self.phone = f"+91-{self.phone}"
        super().save(*args, **kwargs)

class Product(models.Model):
    seller = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'role': UserRole.SELLER_OWNER})
    product_name = models.CharField(max_length=100)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    image = models.ImageField(upload_to=get_image_upload_to, blank=True, null=True)

    def __str__(self):
        return self.product_name

class Contact(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    message = models.TextField()

    def __str__(self):
        return f"{self.name} ({self.email})"

class About(models.Model):
    image = models.ImageField(upload_to=get_image_upload_to, blank=True, null=True)
    about_text = models.TextField()

    def __str__(self):
        return "About Us"

class Cart(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="carts")

    def __str__(self):
        return f"Cart of {self.user.name} - {self.id}"

    def total_items(self):
        return self.cart_items.aggregate(total=models.Sum('quantity'))['total'] or 0

    def total_price(self):
        return sum(item.total_price() for item in self.cart_items.all())

class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="cart_items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    date_added = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.quantity} x {self.product.product_name}"

    def total_price(self):
        return self.quantity * self.product.price

class Checkout(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="checkouts")
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    pincode = models.CharField(max_length=6)
    country = models.CharField(max_length=100)

    def __str__(self):
        return f"Checkout for {self.user.name} - {self.id}"

    def full_address(self):
        return f"{self.address}, {self.city}, {self.state}, {self.pincode}, {self.country}"

class Order(models.Model):
    ORDER_STATUS_CHOICES = [
			("Pending", "Pending"),
			("Processing", "Processing"),
			("Shipped", "Shipped"),
			("Delivered", "Delivered"),
			("Cancelled", "Cancelled"),
		]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="orders")
    status = models.CharField(max_length=20, choices=ORDER_STATUS_CHOICES, default="Pending")
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return f"Order #{self.id} by {self.user.name}"

    def calculate_total_price(self):
        self.total_price = sum(item.total_price() for item in self.order_items.all())
        self.save()

class OrderItem(models.Model):
    STATUS_CHOICES = [
			("pending", "Pending"),
			("ready_to_ship", "Ready_To_Ship"),
			("shipped", "Shipped"),
			("completed", "Completed"),
			("cancelled", "Cancelled"),
		]

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='order_items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending')
    order_date = models.DateField(blank=True, null=True, help_text="The date the item was ordered.")
    dispatch_date = models.DateField(blank=True, null=True, help_text="The date the item was dispatched.")

    def __str__(self):
        return f"{self.quantity} x {self.product.product_name} (Order #{self.order.id})"

    def total_price(self):
        return self.quantity * self.product.price

class BillingAddress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="billing_addresses")
    order = models.OneToOneField("Order", on_delete=models.SET_NULL, related_name="billing_address", null=True, blank=True)

    # Billing Address
    billing_fullname = models.CharField(max_length=255)
    billing_address = models.TextField()
    billing_city = models.CharField(max_length=100)
    billing_state = models.CharField(max_length=100, blank=True, null=True)
    billing_pincode = models.CharField(max_length=6)
    billing_country = models.CharField(max_length=100)
    billing_contact_number = models.CharField(max_length=14)

    # Shipping Address (Now part of the same table)
    shipping_fullname = models.CharField(max_length=255)
    shipping_address = models.TextField()
    shipping_city = models.CharField(max_length=100)
    shipping_state = models.CharField(max_length=100, blank=True, null=True)
    shipping_pincode = models.CharField(max_length=6)
    shipping_country = models.CharField(max_length=100)
    shipping_contact_number = models.CharField(max_length=14)

    def __str__(self):
        return f"Billing Address for {self.billing_fullname} ({self.user.username})"

    def full_billing_address(self):
        return f"{self.billing_address}, {self.billing_city}, {self.billing_state}, {self.billing_pincode}, {self.billing_country}"

    def full_shipping_address(self):
        return f"{self.shipping_address}, {self.shipping_city}, {self.shipping_state}, {self.shipping_pincode}, {self.shipping_country}"

class Payment(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_id = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=[("Pending", "Pending"), ("Completed", "Completed")],
        default="Pending",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payment {self.id} - {self.status}"

class ShippingAddress(models.Model):
    seller = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={"role": UserRole.SELLER_OWNER}, null=True, blank=True)
    BusinessName = models.CharField(max_length=255)
    BusinessAddress = models.TextField()
    City = models.CharField(max_length=100)
    state = models.CharField(max_length=100, blank=True, null=True)
    pincode = models.CharField(max_length=6)
    country = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.BusinessName}, {self.City}"

class BankDetails(models.Model):
    seller = models.ForeignKey(User, on_delete=models.CASCADE)
    BankAccountNo = models.CharField(max_length=50, null=True, blank=True)
    IFSCCode = models.CharField(max_length=50, null=True, blank=True)
    AccountHolderName = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        verbose_name = "Bank Detail"
        verbose_name_plural = "Bank Details"
        ordering = ['AccountHolderName']

    def __str__(self):
        return f"{self.AccountHolderName} - {self.BankAccountNo}"
