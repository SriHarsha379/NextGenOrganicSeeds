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
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_status = models.CharField(max_length=50, default="Pending")  # Pending, Paid
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order {self.id} - {self.full_name} - ₹{self.total_amount}"

