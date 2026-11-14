import os, sys, django

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "seedstore.settings")
django.setup()

from django.db.models import Count, Min
from products.models import Category, Seed

# ── 1. Merge stray "All Seasonal Flower" / "All Season Flower" into canonical ──
print("\nCategory cleanup")
try:
    canonical = Category.objects.get(name="All seasonal")
    stray_names = ["All Seasonal Flower", "All Season Flower"]
    for bad in Category.objects.filter(name__in=stray_names):
        moved = Seed.objects.filter(category=bad).update(category=canonical)
        bad.delete()
        print(f"  OK  Moved {moved} seeds from '{bad.name}' → 'All seasonal' and deleted stray category")
    if not Category.objects.filter(name__in=stray_names).exists():
        print("  OK  No stray categories remain")
except Category.DoesNotExist:
    print("  SKIP  'All seasonal' category not found — check category name in your DB")

# ── 2. Find and remove duplicate products ─────────────────────────────────────
print("\nDuplicate product cleanup")
dupes = (
    Seed.objects.values("name")
    .annotate(count=Count("id"), keep_id=Min("id"))
    .filter(count__gt=1)
)

if not dupes:
    print("  OK  No duplicate products found")

total_removed = 0
for d in dupes:
    name = d["name"]
    keep_id = d["keep_id"]
    # Keep the oldest (lowest id), delete the rest
    to_delete = Seed.objects.filter(name=name).exclude(id=keep_id)
    ids = list(to_delete.values_list("id", flat=True))
    to_delete.delete()
    print(f"  OK  '{name}' — kept id={keep_id}, deleted ids={ids}")
    total_removed += len(ids)

if total_removed:
    print(f"\n  Removed {total_removed} duplicate products total")

print("\nDone.\n")
