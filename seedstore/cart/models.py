from django.db import models
from django.contrib.auth.models import User
from products.models import Seed

class Cart(models.Model):
    # user = models.ForeignKey(User, on_delete=models.CASCADE)
    seed = models.ForeignKey(Seed, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    @property
    def total_price(self):
        return self.quantity * self.seed.price  # Now accessible as an attribute

    def __str__(self):
        return f"{self.user.username} - {self.seed.name} ({self.quantity})"


class Order(models.Model):
    full_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=15)
    address = models.TextField()
    cart_items = models.JSONField(default=list)  # ✅ Set default to an empty list
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_status = models.CharField(max_length=20, choices=[('Pending', 'Pending'), ('Paid', 'Paid')], default='Pending')
    payment_id = models.CharField(max_length=100, blank=True, null=True)  # Razorpay Payment ID
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order #{self.id} - {self.full_name} - {self.payment_status}"

