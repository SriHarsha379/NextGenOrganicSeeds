from django.db import models
from django.contrib.auth.models import User

class Order(models.Model):
    PAYMENT_STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Paid', 'Paid'),
        ('Failed', 'Failed'),
        ('Refunded', 'Refunded'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=15)
    address = models.TextField()
    cart_items = models.JSONField(default=list)
    total_quantity = models.IntegerField(default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='Pending')
    payment_id = models.CharField(max_length=100, blank=True, null=True)
    postal_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    cf_order_id = models.CharField(max_length=100, blank=True, null=True)
    order_token = models.CharField(max_length=255, blank=True, null=True)
    payment_link = models.URLField(max_length=1000, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # ✅ Add this field
    phonepe_order_id = models.CharField(max_length=100, blank=True, null=True, unique=True)

    def save(self, *args, **kwargs):
        self.total_quantity = sum(item.get("quantity", 1) for item in self.cart_items)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Order #{self.id} - {self.user.username} - {self.payment_status}"

