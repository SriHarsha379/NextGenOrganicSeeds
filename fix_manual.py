import os
ROOT = os.path.dirname(os.path.abspath(__file__))

def patch(path, label, old, new):
    full = os.path.join(ROOT, path)
    if not os.path.exists(full):
        print(f"  SKIP (not found): {label}")
        return
    txt = open(full, encoding="utf-8").read()
    if old not in txt:
        print(f"  SKIP (pattern missing): {label}")
        return
    open(full, "w", encoding="utf-8").write(txt.replace(old, new, 1))
    print(f"  OK  {label}")

def overwrite(path, label, content):
    full = os.path.join(ROOT, path)
    open(full, "w", encoding="utf-8").write(content)
    print(f"  OK  {label}")

# ── 1. cart/models.py ────────────────────────────────────────────────────────
print("\ncart/models.py")

# Remove temp_field from Cart
patch(
    "cart/models.py",
    "Remove temp_field from Cart model",
    '    temp_field = models.BooleanField(default=True)  # 👈 TEMP FIELD\n\n',
    '',
)

# Remove the entire stale Order model from cart/models.py
patch(
    "cart/models.py",
    "Remove stale legacy Order model (real one lives in orders/models.py)",
    '''

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

''',
    '\n',
)

# ── 2. context_processors.py ─────────────────────────────────────────────────
print("\ncontext_processors.py")

# The file uses a relative import which is broken at project root.
# The app already uses session-based cart counts in every view directly,
# so this file is unused. Replace it with a no-op safe version + comment.
overwrite(
    "context_processors.py",
    "Fix broken relative import (was: from .models import Cart)",
    '''# This file is unused — cart counts are injected directly in each view.
# Kept as a placeholder so any template reference to cart_count still works
# safely without raising an error if wired up accidentally.

def cart_count(request):
    """Safe no-op context processor. Cart count is managed via session in views."""
    cart = request.session.get("cart", {})
    return {"cart_count": len(cart)}
''',
)

# ── 3. products/utils/phonepe_client.py ──────────────────────────────────────
print("\nproducts/utils/phonepe_client.py")

overwrite(
    "products/utils/phonepe_client.py",
    "Wrap PhonePe client init in ImproperlyConfigured guard",
    '''from django.core.exceptions import ImproperlyConfigured
from decouple import config, UndefinedValueError

def _build_client():
    try:
        from phonepe.sdk.pg.payments.v2.standard_checkout_client import StandardCheckoutClient
        from phonepe.sdk.pg.env import Env

        phonepe_env = config("PHONEPE_ENV", default="SANDBOX")
        env = Env.PRODUCTION if phonepe_env == "PRODUCTION" else Env.SANDBOX

        return StandardCheckoutClient.get_instance(
            client_id=config("PHONEPE_CLIENT_ID"),
            client_secret=config("PHONEPE_CLIENT_SECRET"),
            client_version=config("PHONEPE_CLIENT_VERSION", cast=int),
            env=env,
        )
    except UndefinedValueError as e:
        raise ImproperlyConfigured(
            f"PhonePe configuration missing from .env: {e}. "
            "Set PHONEPE_CLIENT_ID, PHONEPE_CLIENT_SECRET, and PHONEPE_CLIENT_VERSION."
        ) from e
    except Exception as e:
        raise ImproperlyConfigured(
            f"Failed to initialise PhonePe SDK: {e}"
        ) from e

client = _build_client()
''',
)

print("\nDone.\n")
