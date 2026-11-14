from django.contrib import admin
from .models import Order, Coupon, CouponRedemption


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "full_name", "email", "phone", "total_amount", "payment_status", "created_at")
    list_filter = ("payment_status",)
    search_fields = ("full_name", "email", "phone", "phonepe_order_id")
    readonly_fields = (
        "payment_status", "total_amount", "payment_id",
        "phonepe_order_id", "created_at", "session_key",
    )
    ordering = ("-created_at",)


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ("code", "percent_off", "active", "valid_until")
    list_filter = ("active",)


@admin.register(CouponRedemption)
class CouponRedemptionAdmin(admin.ModelAdmin):
    list_display = ("coupon", "email", "redeemed_at")
    readonly_fields = ("coupon", "email", "order", "redeemed_at")

