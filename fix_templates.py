import os, re
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
        os.remove(full); print(f"  OK  Deleted {label}")
    else:
        print(f"  SKIP (not found): {label}")

print("\ncart/templates/cart/checkout.html")

# Fix broken template tag — {{% → {%
patch(
    "cart/templates/cart/checkout.html",
    "Fix broken template tag {{% -> {%",
    "{{% for item in cart_items %}",
    "{% for item in cart_items %}",
)

# Fix double redirect — remove the outer redirect, keep only the one inside .then()
patch(
    "cart/templates/cart/checkout.html",
    "Fix double redirect — cart never cleared before payment",
    '''}).then(() => {
    document.getElementById("overlay-loader").style.display = "block";
    window.location.href = data.payment_link;
});


                window.location.href = data.payment_link;''',
    '''}).then(() => {
    document.getElementById("overlay-loader").style.display = "block";
    window.location.href = data.payment_link;
});''',
)

# Remove payment_status from client payload (server ignores it, reduces noise)
patch(
    "cart/templates/cart/checkout.html",
    "Remove client-sent payment_status from order payload",
    '                coupon_code: appliedCoupon ? appliedCoupon.code : "",\n                payment_status: "Pending",',
    '                coupon_code: appliedCoupon ? appliedCoupon.code : "",',
)

print("\nseedstore/templates/base.html")

# Fix wrong WhatsApp number
patch(
    "seedstore/templates/base.html",
    "Fix WhatsApp number: placeholder 9876543210 -> real 7483847243",
    "https://wa.me/919876543210?text=Hi%20Hasafarm!%20I%20need%20help%20choosing%20seeds%20%F0%9F%8C%B1",
    "https://wa.me/917483847243?text=Hi%20Hasafarm!%20I%20need%20help%20choosing%20seeds%20%F0%9F%8C%B1",
)

# Fix hardcoded /login/ in modal
patch(
    "seedstore/templates/base.html",
    "Fix hardcoded /login/ -> {% url 'login' %}",
    '<a href="/login/" class="modal-login-btn">Log In</a>',
    "<a href=\"{% url 'login' %}\" class=\"modal-login-btn\">Log In</a>",
)

# Fix copyright year
patch(
    "seedstore/templates/base.html",
    "Update copyright year 2025 -> 2026",
    "© 2025 Hasa Farm. All Rights Reserved.",
    "© 2026 Hasa Farm. All Rights Reserved.",
)

# Fix deprecated performance.navigation.type
patch(
    "seedstore/templates/base.html",
    "Fix deprecated performance.navigation.type API",
    "if (performance.navigation.type === 2) { window.location.reload(true); }",
    """const navEntry = performance.getEntriesByType('navigation')[0];
    if (navEntry && navEntry.type === 'back_forward') { window.location.reload(true); }""",
)

print("\ncart/templates/cart/order_success.html")

# Fix broken /contact/ link
patch(
    "cart/templates/cart/order_success.html",
    "Fix broken /contact/ link -> mailto",
    'please <a href="/contact/">contact us</a>.',
    'please <a href="mailto:contact@hasafarm.com">contact us</a>.',
)

print("\naccounts/templates/accounts/login.html")

# Fix |safe on messages — scope it only to messages that need HTML
patch(
    "accounts/templates/accounts/login.html",
    "Remove |safe from flash messages (XSS risk)",
    "<div class=\"alert alert-{{ message.tags }}\">{{ message|safe }}</div>",
    "<div class=\"alert alert-{{ message.tags }}\">{{ message }}</div>",
)

print("\nStale duplicate template")
delete_file(
    "seedstore/accounts/templates/emails/welcome_email.html",
    "Stale duplicate welcome_email at wrong path",
)

print("\nDone.\n")
print("Manual steps:")
print("  1. Add /get-cart-count/ endpoint (or remove the fetch from base.html):")
print("     The fetch silently 404s on every page. Quickest fix — remove it")
print("     since cart_count is already passed correctly from view context.")
print("")
print("  2. Add a /contact/ page or redirect, or the order_success fix above")
print("     (mailto link) covers it.")
print("")
print("  3. The register link in the login error message uses |safe intentionally.")
print("     If you want HTML in future messages, use a custom message tag instead.")
