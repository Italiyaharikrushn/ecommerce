# Generated by Django 5.1.1 on 2025-01-11 10:00

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ecom', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='role',
            field=models.CharField(choices=[('ROLE_CUSTOMER', 'Customer'), ('ROLE_SELLER_OWNER', 'Seller Owner'), ('ROLE_ADMIN', 'Admin')], max_length=21),
        ),
    ]