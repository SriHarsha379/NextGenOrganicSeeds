import os
ROOT = os.path.dirname(os.path.abspath(__file__))

def patch(path, label, old, new):
    full = os.path.join(ROOT, path)
    if not os.path.exists(full):
        print(f"  SKIP (not found): {label}"); return
    txt = open(full, encoding="utf-8").read()
    if old not in txt:
        print(f"  SKIP (pattern missing): {label}"); return
    open(full, "w", encoding="utf-8").write(txt.replace(old, new, 1))
    print(f"  OK  {label}")

def delete_file(path, label):
    full = os.path.join(ROOT, path)
    if os.path.exists(full):
        os.remove(full)
        print(f"  OK  Deleted {label}")
    else:
        print(f"  SKIP (not found): {label}")

# ── 1. Fix invisible products: query both "All seasonal" category name variants ──
print("\nproducts/views.py")
patch(
    "products/views.py",
    "Fix render_seeds_by_category to handle multiple category name variants",
    '''def render_seeds_by_category(request, category_name, template_name):
    category = get_object_or_404(Category, name=category_name)
    seeds = Seed.objects.filter(category=category)

    cart = request.session.get('cart', {})
    unique_item_count = len(cart)

    return render(request, template_name, {
        'seeds': seeds,
        'cart_count': unique_item_count,
    })''',
    '''def render_seeds_by_category(request, category_name, template_name):
    # Some seeds were imported under variant spellings (e.g. "All Seasonal Flower"
    # vs "All seasonal"). Query all matching categories case-insensitively so no
    # products are silently hidden.
    CATEGORY_ALIASES = {
        "All seasonal": ["All seasonal", "All Seasonal Flower", "All Season Flower"],
    }
    names = CATEGORY_ALIASES.get(category_name, [category_name])
    categories = Category.objects.filter(name__in=names)
    if not categories.exists():
        from django.http import Http404
        raise Http404(f"Category '{category_name}' not found")
    seeds = Seed.objects.filter(category__in=categories)

    cart = request.session.get('cart', {})
    unique_item_count = len(cart)

    return render(request, template_name, {
        'seeds': seeds,
        'cart_count': unique_item_count,
    })''',
)

# ── 2. Add CSV files to .gitignore ───────────────────────────────────────────
print("\n.gitignore")
patch(
    ".gitignore",
    "Add seeds_data.csv* to .gitignore",
    "# ======================\n# Local databases",
    "# ======================\n# Data files (contain pricing — don't version)\n# ======================\nseeds_data.csv\nseeds_data.csv.save\n\n# ======================\n# Local databases",
)

# ── 3. Delete orphaned root-level HTML files ─────────────────────────────────
print("\nRoot-level orphaned files")
delete_file("context_processors.html", "context_processors.html (IDE-generated junk)")
delete_file("maintenance.html", "maintenance.html (unwired, served nothing)")

print("\nDone.\n")
print("Manual steps:")
print("  1. Fix duplicate products in DB:")
print("     python3 manage.py shell")
print("     >>> from products.models import Seed")
print("     >>> # Review: Seed.objects.values('name').annotate(c=Count('id')).filter(c__gt=1)")
print("     >>> # Then delete the duplicate with lower stock or older id")
print("")
print("  2. Merge stray category into the canonical one:")
print("     python3 manage.py shell")
print("     >>> from products.models import Category, Seed")
print("     >>> canonical = Category.objects.get(name='All seasonal')")
print("     >>> for bad in Category.objects.filter(name__in=['All Seasonal Flower','All Season Flower']):")
print("     ...     Seed.objects.filter(category=bad).update(category=canonical)")
print("     ...     bad.delete()")
print("")
print("  3. Never re-import seeds_data.csv — stock is hardcoded to 100.")
print("     Manage stock through /admin/inventory/ instead.")
print("")
print("  4. git rm --cached seeds_data.csv seeds_data.csv.save")
print("     git commit -m 'chore: stop tracking product CSV'")
