from django.db import models
from django.contrib.auth.models import User


class Coupon(models.Model):
    """A promo code, e.g. COMEBACK10, with an expiry and a per-customer usage limit."""
    code = models.CharField(max_length=30, unique=True, db_index=True)
    percent_off = models.PositiveIntegerField(help_text="e.g. 10 for 10% off")
    active = models.BooleanField(default=True)
    valid_until = models.DateTimeField(help_text="Coupon stops working after this date/time.")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.code} ({self.percent_off}% off, valid until {self.valid_until:%Y-%m-%d})"


class CouponRedemption(models.Model):
    """Tracks that a given email has already used a given coupon, to prevent repeat use."""
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name="redemptions")
    email = models.EmailField(db_index=True)
    order = models.ForeignKey("Order", on_delete=models.SET_NULL, null=True, blank=True)
    redeemed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("coupon", "email")

    def __str__(self):
        return f"{self.email} used {self.coupon.code}"


class Order(models.Model):
    PAYMENT_STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Paid', 'Paid'),
        ('Failed', 'Failed'),
        ('Cancelled', 'Cancelled'),
        ('Refunded', 'Refunded'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)  # ✅ allow guests
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
    coupon_code = models.CharField(max_length=30, blank=True, null=True)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    cf_order_id = models.CharField(max_length=100, blank=True, null=True)
    order_token = models.CharField(max_length=255, blank=True, null=True)
    payment_link = models.URLField(max_length=1000, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    session_key = models.CharField(max_length=40, blank=True, null=True)
    is_printed = models.BooleanField(default=False)
    # ✅ Add this field
    phonepe_order_id = models.CharField(max_length=100, blank=True, null=True, unique=True)

    def save(self, *args, **kwargs):
        # Only recompute total_quantity on full saves, not on partial update_fields saves
        # (partial saves are used by the webhook to update payment_status only).
        if not kwargs.get("update_fields"):
            self.total_quantity = sum(item.get("quantity", 1) for item in self.cart_items)
        super().save(*args, **kwargs)

    def __str__(self):
        username = self.user.username if self.user else "Guest"
        return f"Order #{self.id} - {username} - {self.payment_status}"


