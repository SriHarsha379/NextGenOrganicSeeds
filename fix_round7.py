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

def write_file(path, label, content):
    full = os.path.join(ROOT, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    open(full, "w", encoding="utf-8").write(content)
    print(f"  OK  {label}")

# ── 1. Seed.category: CASCADE → SET_NULL ─────────────────────────────────────
print("\nproducts/models.py")
patch(
    "products/models.py",
    "Seed.category: CASCADE -> SET_NULL (deleting category must not wipe products)",
    "    category = models.ForeignKey(Category, on_delete=models.CASCADE, null=True, blank=True)",
    "    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)",
)

# ── 2. Category.name: add case-insensitive uniqueness via db_collation ────────
# Simplest portable fix: add a unique index note — actual CI uniqueness needs
# a custom migration. We add a validator instead to catch it at the app layer.
print("\nproducts/models.py — add case-insensitive category name cleaning")
patch(
    "products/models.py",
    "Category.save(): normalize name casing to prevent near-duplicates",
    '''class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name''',
    '''class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def save(self, *args, **kwargs):
        # Normalize to title-case on save so "native", "Native", "NATIVE"
        # all become "Native" and hit the unique constraint correctly.
        self.name = self.name.strip().title()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name''',
)

# ── 3. Add updated_at to Order ────────────────────────────────────────────────
print("\norders/models.py — add updated_at")
patch(
    "orders/models.py",
    "Order: add updated_at timestamp",
    "    created_at = models.DateTimeField(auto_now_add=True)",
    "    created_at = models.DateTimeField(auto_now_add=True)\n    updated_at = models.DateTimeField(auto_now=True)",
)

# ── 4. Add updated_at to Seed ─────────────────────────────────────────────────
print("\nproducts/models.py — add updated_at to Seed")
patch(
    "products/models.py",
    "Seed: add updated_at for price/stock change tracking",
    "    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)",
    "    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)\n    updated_at = models.DateTimeField(auto_now=True)",
)

# ── 5. robots.txt ─────────────────────────────────────────────────────────────
print("\nrobots.txt")
write_file(
    "static/robots.txt",
    "Create robots.txt to block admin/checkout from search engines",
    """User-agent: *
Disallow: /admin/
Disallow: /django-admin/
Disallow: /cart/
Disallow: /orders/
Disallow: /accounts/login/
Disallow: /accounts/register/
Disallow: /accounts/reset-password/
Disallow: /phonepe/
Disallow: /parse-order-data/

# Allow product and informational pages
Allow: /seeds/
Allow: /seeds/privacy-policy/
Allow: /seeds/terms-conditions/
Allow: /seeds/shipping/
Allow: /seeds/refund/

Sitemap: https://hasafarm.com/sitemap.xml
""",
)

# ── 6. Update .env.example with all new variables ─────────────────────────────
print("\n.env.example")
patch(
    ".env.example",
    "Add SITE_URL, DATABASE_URL, SENTRY_DSN, HSTS_PRELOAD to .env.example",
    "# ─── Django ─────────────────────────────────────────────────────────────────\nDEBUG=False",
    '''# ─── Django ─────────────────────────────────────────────────────────────────
DEBUG=False
# The public URL of this deployment — used in email links (unsubscribe, abandoned cart).
SITE_URL=https://hasafarm.com

# ─── Database ────────────────────────────────────────────────────────────────
# PostgreSQL strongly recommended for production. Leave blank to use SQLite.
# Format: postgres://USER:PASSWORD@HOST:PORT/DBNAME
# DATABASE_URL=postgres://seedstore:yourpassword@localhost:5432/seedstore

# ─── Error tracking (Sentry) ─────────────────────────────────────────────────
# Get your DSN from sentry.io → Project Settings → Client Keys.
# Leave blank to disable — the app works fine without it.
SENTRY_DSN=

# ─── HSTS Preload (irreversible — read before enabling) ──────────────────────
# Only set to True when you are 100% sure this domain will ALWAYS serve HTTPS.
# Once submitted to the browser preload list it can take months to remove.
HSTS_PRELOAD=False''',
)

print("\nDone.\n")
print("Manual steps:")
print("  1. Migrate for model changes:")
print("     python3 manage.py makemigrations products orders --name round7_model_updates")
print("     python3 manage.py migrate")
print("")
print("  2. Wire robots.txt into urls.py:")
print("     Add this to seedstore/urls.py urlpatterns:")
print("     from django.views.generic import TemplateView")
print("     path('robots.txt', TemplateView.as_view(")
print("         template_name='robots.txt',")
print("         content_type='text/plain'), name='robots'),")
print("     (and move static/robots.txt to seedstore/templates/robots.txt)")
