import os, sys, django

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "seedstore.settings")
django.setup()

from django.db.models import F
from orders.models import Order
from products.models import Seed

# ── Restore stock for all existing Failed/Cancelled/Pending orders ────────────
print("\nStock restoration for unpaid orders")

unpaid = Order.objects.filter(payment_status__in=["Failed", "Cancelled", "Pending"])
print(f"  Found {unpaid.count()} unpaid orders to process")

restored = {}   # seed_id -> total qty restored
skipped  = []

for order in unpaid:
    for item in (order.cart_items or []):
        seed_id = item.get("id")
        qty     = int(item.get("quantity", 1))
        if not seed_id or qty <= 0:
            continue
        try:
            Seed.objects.filter(id=seed_id).update(stock=F("stock") + qty)
            restored[seed_id] = restored.get(seed_id, 0) + qty
        except Exception as e:
            skipped.append(f"seed_id={seed_id} qty={qty}: {e}")

if restored:
    # Print a summary with seed names
    seed_names = {s.id: s.name for s in Seed.objects.filter(id__in=restored)}
    print(f"\n  Stock restored ({len(restored)} products):")
    for sid, qty in sorted(restored.items(), key=lambda x: -x[1]):
        print(f"    +{qty:3d}  {seed_names.get(sid, f'[id={sid}]')}")
else:
    print("  No stock to restore (no unpaid orders with cart items)")

if skipped:
    print("\n  Could not restore:")
    for s in skipped:
        print(f"    {s}")

print("\nDone.\n")
print("NOTE: Pending orders include active checkouts in progress.")
print("If any customer is currently mid-payment, their stock was just un-reserved.")
print("Those orders will fail at the stock check if they try to retry — which is correct.")
