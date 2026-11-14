import os, re
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

def delete_file(path, label):
    full = os.path.join(ROOT, path)
    if os.path.exists(full):
        os.remove(full)
        print(f"  OK  Deleted: {label}")
    else:
        print(f"  SKIP (not found): {label}")

print("\nadminpanel/views.py")

# Fix seed_delete — require POST
patch(
    "adminpanel/views.py",
    "seed_delete: require POST to prevent CSRF-via-GET deletion",
    '@admin_required\ndef seed_delete(request, id):\n    seed = get_object_or_404(Seed, id=id)\n    seed.delete()\n    return redirect(\'adminpanel:seed_list\')',
    '@admin_required\ndef seed_delete(request, id):\n    if request.method != "POST":\n        from django.http import HttpResponseNotAllowed\n        return HttpResponseNotAllowed(["POST"])\n    seed = get_object_or_404(Seed, id=id)\n    seed.delete()\n    return redirect(\'adminpanel:seed_list\')',
)

print("\nproducts/views.py")

# Remove unused PhonePe import
patch(
    "products/views.py",
    "Remove unused PhonePe client import (crashes app if env vars missing)",
    'from .utils.phonepe_client import client\n',
    '',
)

# Remove unused login_required import
patch(
    "products/views.py",
    "Remove unused login_required import",
    'from django.contrib.auth.decorators import login_required\n',
    '',
)

# Remove unused Cart import
patch(
    "products/views.py",
    "Remove unused Cart import",
    'from cart.models import Cart  # Import the Cart model\n',
    '',
)

print("\naccounts/urls.py")

# Remove dead duplicate logout URL
patch(
    "accounts/urls.py",
    "Remove dead duplicate LogoutView (shadowed by user_logout above it)",
    "    path('logout/', LogoutView.as_view(next_page='login'), name='logout'),\n",
    '',
)

print("\norders/views.py")

# Add @login_required to download_invoice
patch(
    "orders/views.py",
    "Add @login_required to download_invoice",
    'def download_invoice(request, order_id):',
    '@login_required\ndef download_invoice(request, order_id):',
)

# Add @login_required to reorder
patch(
    "orders/views.py",
    "Add @login_required to reorder",
    'def reorder(request, order_id):\n    order = get_object_or_404(Order, id=order_id, user=request.user)',
    '@login_required\ndef reorder(request, order_id):\n    order = get_object_or_404(Order, id=order_id, user=request.user)',
)

print("\naccounts/models.py")

# Fix CampaignSend.sent_at: auto_now → auto_now_add
patch(
    "accounts/models.py",
    "CampaignSend.sent_at: use auto_now_add (preserve original send time)",
    '    sent_at = models.DateTimeField(auto_now=True)',
    '    sent_at = models.DateTimeField(auto_now_add=True)',
)

print("\nroot utils.py")
delete_file("utils.py", "Dead UPI utils.py with hardcoded merchant@upi placeholder")

print("\nDone.\n")
print("Manual steps remaining:")
print("  1. Remove cart/models.py Order model + temp_field (needs a migration)")
print("  2. Fix context_processors.py relative import (or delete it if unused)")
print("  3. Wrap phonepe_client.py init in try/except ImproperlyConfigured")
