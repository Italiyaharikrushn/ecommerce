from django.contrib import admin
from .models import Product, About, Contact, ShippingAddress, BankDetails

# Register your models here.
admin.site.register(Product)
admin.site.register(About)
admin.site.register(Contact)
admin.site.register(ShippingAddress)
admin.site.register(BankDetails)
