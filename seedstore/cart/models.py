from django.db import models
from django.contrib.auth.models import User
from products.models import Seed

class Cart(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    seed = models.ForeignKey(Seed, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    temp_field = models.BooleanField(default=True)  # 👈 TEMP FIELD

    @property
    def total_price(self):
        return self.quantity * self.seed.price

    def __str__(self):
        return f"{self.user.username} - {self.seed.name} ({self.quantity})"


class Order(models.Model):
    full_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=15)
    address_line1 = models.CharField(max_length=255)  # ✅ Street Address
    address_line2 = models.CharField(max_length=255, blank=True, null=True)  # ✅ Optional (Apartment, Suite, etc.)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=10)
    country = models.CharField(max_length=100, default="India")  # Default to India

    cart_items = models.JSONField(default=list)
    total_quantity = models.IntegerField(default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_status = models.CharField(max_length=20, choices=[('Pending', 'Pending'), ('Paid', 'Paid')], default='Pending')
    payment_id = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        """Automatically calculate total quantity before saving"""
        self.total_quantity = sum(item.get("quantity", 1) for item in self.cart_items)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Order #{self.id} - {self.full_name} - {self.payment_status}"


