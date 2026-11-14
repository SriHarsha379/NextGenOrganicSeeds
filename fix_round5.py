import os, sys, django

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

def patch(path, label, old, new):
    full = os.path.join(ROOT, path)
    if not os.path.exists(full):
        print(f"  SKIP (not found): {label}"); return
    txt = open(full, encoding="utf-8").read()
    if old not in txt:
        print(f"  SKIP (pattern missing): {label}"); return
    open(full, "w", encoding="utf-8").write(txt.replace(old, new, 1))
    print(f"  OK  {label}")

# ── 1. Restore stock on Failed/Cancelled in webhook ──────────────────────────
print("\ncart/views.py — restore stock on Failed/Cancelled")
patch(
    "cart/views.py",
    "Restore stock when order is cancelled or failed",
    '''    order.refresh_from_db()

    # ── 7. Send notification emails (only when status actually changed) ───────
    if status_changed:
        _send_order_status_emails(order, new_status)

    return JsonResponse({"message": "Webhook handled"}, status=200)''',
    '''    order.refresh_from_db()

    # ── 7. Restore stock on Failed/Cancelled ─────────────────────────────────
    if status_changed and new_status in ("Failed", "Cancelled"):
        _restore_order_stock(order)

    # ── 8. Send notification emails (only when status actually changed) ───────
    if status_changed:
        _send_order_status_emails(order, new_status)

    return JsonResponse({"message": "Webhook handled"}, status=200)''',
)

# Add the _restore_order_stock helper right before _send_order_status_emails
patch(
    "cart/views.py",
    "Add _restore_order_stock helper",
    "def _send_order_status_emails(order, new_status):",
    '''def _restore_order_stock(order):
    """Return stock to each seed when a payment fails or is cancelled.
    Uses select_for_update to prevent races with concurrent webhooks."""
    try:
        with transaction.atomic():
            for item in (order.cart_items or []):
                try:
                    seed = Seed.objects.select_for_update().get(id=item["id"])
                    qty = int(item.get("quantity", 1))
                    seed.stock += qty
                    seed.save(update_fields=["stock"])
                except Seed.DoesNotExist:
                    logger.warning("⚠️ Could not restore stock for missing seed id=%s", item.get("id"))
                except Exception as exc:
                    logger.error("❌ Stock restore error for seed id=%s: %s", item.get("id"), exc)
        logger.info("✅ Stock restored for order #%s", order.id)
    except Exception as e:
        logger.error("❌ Failed to restore stock for order #%s: %s", order.id, e)


def _send_order_status_emails(order, new_status):''',
)

# ── 2. Order.user CASCADE → SET_NULL ─────────────────────────────────────────
print("\norders/models.py — Order.user CASCADE -> SET_NULL")
patch(
    "orders/models.py",
    "Order.user: on_delete=CASCADE -> SET_NULL (preserve orders when user deleted)",
    "    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)  # ✅ allow guests",
    "    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)  # preserve orders if user is deleted",
)

# ── 3. STATIC_ROOT: use BASE_DIR instead of hardcoded path ───────────────────
print("\nseedstore/settings.py — fix hardcoded STATIC_ROOT")
patch(
    "seedstore/settings.py",
    "STATIC_ROOT: replace hardcoded server path with BASE_DIR",
    'STATIC_ROOT = "/home/seedstore/static/"',
    'STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")',
)

# ── 4. Fix products/admin.py search_fields FK traversal ──────────────────────
print("\nproducts/admin.py — fix search_fields category traversal")
patch(
    "products/admin.py",
    "Fix search_fields: category -> category__name",
    "    search_fields = ('name', 'category')",
    "    search_fields = ('name', 'category__name')",
)

# ── 5. Harden orders/admin.py — make sensitive fields read-only ──────────────
print("\norders/admin.py — make payment fields read-only")
patch(
    "orders/admin.py",
    "Make payment_status and total_amount read-only in admin",
    "from django.contrib import admin\nfrom .models import Order\n\nadmin.site.register(Order)",
    '''from django.contrib import admin
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
''',
)

# ── 6. Suppress unused DB Cart from admin ────────────────────────────────────
print("\ncart/admin.py — remove legacy Cart from admin")
patch(
    "cart/admin.py",
    "Remove legacy DB Cart from admin (cart is session-based now)",
    "from django.contrib import admin\nfrom .models import Cart\n\nadmin.site.register(Cart)",
    "# Cart is session-based — the DB Cart model is legacy and not shown in admin.",
)

print("\nDone.\n")
print("Manual steps:")
print("  1. Run migrations for Order.user SET_NULL change:")
print("     python3 manage.py makemigrations orders --name order_user_set_null")
print("     python3 manage.py migrate")
print("")
print("  2. Untrack .idea/ from git:")
print("     git rm -r --cached .idea/")
print("     git commit -m 'chore: untrack .idea/ IDE config'")
print("")
print("  3. Audit existing Failed/Cancelled orders and restore stock manually:")
print("     python3 manage.py shell -c \"")
print("     from orders.models import Order; from products.models import Seed")
print("     from django.db import transaction")
print("     for o in Order.objects.filter(payment_status__in=['Failed','Cancelled']):")
print("         for item in o.cart_items:")
print("             Seed.objects.filter(id=item['id']).update(stock=F('stock')+item.get('quantity',1))")
print("     \"")
