#!/usr/bin/env python3
"""
fix_critical_issues.py
Run from the project root: python fix_critical_issues.py

Applies all Critical + High severity fixes from the security audit.
"""
import os, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
skipped = []

def p(path):
    return os.path.join(ROOT, path)

def patch(path, label, old, new):
    full = p(path)
    if not os.path.exists(full):
        skipped.append(f"[FILE NOT FOUND]  {label}  →  {path}")
        return
    txt = open(full, encoding="utf-8").read()
    if old not in txt:
        skipped.append(f"[PATTERN MISSING] {label}  →  {path}")
        return
    open(full, "w", encoding="utf-8").write(txt.replace(old, new, 1))
    print(f"  ✅  {label}")


# ═══════════════════════════════════════════════════════════════════════════════
# 1. seedstore/settings.py
# ═══════════════════════════════════════════════════════════════════════════════
print("\n📄 seedstore/settings.py")

patch(
    "seedstore/settings.py",
    "LOGIN_URL: point to user login, not admin login",
    "LOGIN_URL = '/admin/login/'",
    "LOGIN_URL = '/accounts/login/'",
)


# ═══════════════════════════════════════════════════════════════════════════════
# 2. orders/views.py
# ═══════════════════════════════════════════════════════════════════════════════
print("\n📄 orders/views.py")

# 2a. payment_success — was unauthenticated AND silently marked orders as paid
patch(
    "orders/views.py",
    "Neuter legacy payment_success (no auth, no verification)",
    """\ndef payment_success(request):
    # Here, you should verify the payment via UPI API before updating order status
    orders = Order.objects.filter(user=request.user, status="Pending")
    orders.update(status="Completed")
    return render(request, "orders/payment_success.html")""",
    """
@login_required
def payment_success(request):
    # LEGACY STUB — real payment confirmation is handled by the PhonePe webhook
    # and the order_success view.  This endpoint intentionally no longer mutates
    # any order state; it exists only to avoid 404s from old links.
    return render(request, "orders/payment_success.html")""",
)

# 2b. download_invoice — hardcoded Windows dev-machine path
patch(
    "orders/views.py",
    "Fix hardcoded Windows logo path in download_invoice",
    "    logo_path = os.path.join('E:/imp/python project/NextGenOrganicSeeds/static/images/hasa_organic_seeds.png')",
    "    logo_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'hasa_organic_seeds.png')",
)


# ═══════════════════════════════════════════════════════════════════════════════
# 3. cart/views.py
# ═══════════════════════════════════════════════════════════════════════════════
print("\n📄 cart/views.py")

# 3a. process_order — remove @csrf_exempt
patch(
    "cart/views.py",
    "Remove @csrf_exempt from process_order",
    "@csrf_exempt\ndef process_order(request):",
    "def process_order(request):",
)

# 3b. process_order — replace client-trusted total_amount with server-computed total
#     The original code blindly trusted data["total_amount"] from the browser.
#     We now recompute from DB prices so the client cannot manipulate the charge.
patch(
    "cart/views.py",
    "Recompute total server-side from DB prices (critical price-manipulation fix)",
    """\        postal_charge = Decimal("80.00")
        try:
            base_amount = Decimal(str(data["total_amount"]))
            if base_amount <= 0:
                raise ValueError("Invalid total_amount")
        except (ValueError, TypeError, KeyError):
            return JsonResponse({"error": "Invalid amount format"}, status=400)""",
    """\        # ── Server-side price recomputation ──────────────────────────────────────
        # Never trust total_amount sent by the browser — recompute from DB prices.
        db_subtotal = Decimal("0.00")
        for item in data["cart_items"]:
            try:
                _seed = Seed.objects.get(id=item["id"])
            except Seed.DoesNotExist:
                return JsonResponse(
                    {"error": f"Item not found: {item.get('id')}"}, status=400
                )
            _qty = int(item.get("quantity", 1))
            if _qty <= 0:
                return JsonResponse(
                    {"error": f"Invalid quantity for {_seed.name}"}, status=400
                )
            db_subtotal += _seed.price * _qty

        if db_subtotal <= 0:
            return JsonResponse({"error": "Cart is empty or prices are zero"}, status=400)

        base_amount = db_subtotal
        # Free shipping on orders ≥ ₹499 (mirrors the checkout view logic)
        postal_charge = Decimal("0.00") if db_subtotal >= Decimal("499.00") else Decimal("80.00")""",
)

# 3c. retry_payment — was inaccessible to logged-in users whose session expired
patch(
    "cart/views.py",
    "Fix retry_payment: allow authenticated order owner, not just guest session",
    """\def retry_payment(request, phonepe_order_id):
    order = get_object_or_404(Order, phonepe_order_id__iexact=phonepe_order_id)

    # 🔐 Guest session validation
    session_guest_id = str(request.session.get("guest_order_id"))
    if session_guest_id != str(order.id):
        return HttpResponseForbidden("Unauthorized access to this guest order.")

    # ✅ Retry logic
    if order.payment_status != "Paid":
        return redirect(order.payment_link or "home")

    # Already paid — show success
    return redirect("order_success", phonepe_order_id=order.phonepe_order_id)""",
    """\def retry_payment(request, phonepe_order_id):
    order = get_object_or_404(Order, phonepe_order_id__iexact=phonepe_order_id)

    # Allow the authenticated order owner OR a guest with the matching session key.
    is_owner  = request.user.is_authenticated and order.user == request.user
    is_guest  = str(request.session.get("guest_order_id", "")) == str(order.id)

    if not (is_owner or is_guest):
        return HttpResponseForbidden("Unauthorized access to this order.")

    # Already paid — go to confirmation
    if order.payment_status == "Paid":
        return redirect("order_success", phonepe_order_id=order.phonepe_order_id)

    # Not yet paid — send back to payment link
    return redirect(order.payment_link or "home")""",
)


# ═══════════════════════════════════════════════════════════════════════════════
# 4. accounts/views.py
# ═══════════════════════════════════════════════════════════════════════════════
print("\n📄 accounts/views.py")

# Remove the broken duplicate AutoLogout class.
# It references `timedelta` which is never imported in this file → NameError crash.
# The correct implementation already lives in accounts/middleware.py.
patch(
    "accounts/views.py",
    "Remove broken duplicate AutoLogout (timedelta NameError); canonical copy is in middleware.py",
    """\nclass AutoLogout:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            last_activity = request.session.get('last_activity')
            if last_activity:
                idle_time = now() - last_activity
                if idle_time > timedelta(seconds=3600):  # 1 hour timeout
                    del request.session['last_activity']
                    return redirect('logout')  # Redirect to logout page

            request.session['last_activity'] = now()

        return self.get_response(request)\n""",
    "\n# AutoLogout middleware lives in accounts/middleware.py — removed broken duplicate.\n",
)


# ═══════════════════════════════════════════════════════════════════════════════
# 5. .gitignore
# ═══════════════════════════════════════════════════════════════════════════════
print("\n📄 .gitignore")

patch(
    ".gitignore",
    "Add .DS_Store and .coverage",
    "# ======================\n# Django secrets",
    "# ======================\n# macOS / editor junk\n# ======================\n.DS_Store\n.coverage\nhtmlcov/\n\n# ======================\n# Django secrets",
)


# ═══════════════════════════════════════════════════════════════════════════════
# 6. requirements.txt
# ═══════════════════════════════════════════════════════════════════════════════
print("\n📄 requirements.txt")

patch(
    "requirements.txt",
    "Remove unused cashfree-sdk",
    "cashfree-sdk==0.1.3\n",
    "",
)


# ═══════════════════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "═" * 65)
if skipped:
    print("⚠️  Skipped patches — review manually:\n")
    for s in skipped:
        print(f"   {s}")
    print()
else:
    print("✅  All patches applied cleanly.\n")

print("""\
┌─────────────────────────────────────────────────────────────┐
│  MANUAL STEPS STILL REQUIRED AFTER RUNNING THIS SCRIPT      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. WEBHOOK AUTH — set both variables in .env:              │
│       PHONEPE_WEBHOOK_USER=<value from PhonePe dashboard>   │
│       PHONEPE_WEBHOOK_PASSWORD=<value from PhonePe dashboard>│
│     Without this, fake Cancelled/Failed webhooks are        │
│     accepted and can cancel real paid orders.               │
│                                                             │
│  2. SWITCH TO POSTGRESQL — in settings.py replace:         │
│       'ENGINE': 'django.db.backends.sqlite3'                │
│     with PostgreSQL (psycopg2 is already in requirements).  │
│     SQLite + select_for_update() = data corruption risk.    │
│     Recommended: use dj-database-url + DATABASE_URL in .env │
│                                                             │
│  3. LOGIN RATE LIMITING — install django-axes:              │
│       pip install django-axes                               │
│       Add 'axes' to INSTALLED_APPS                          │
│       Add 'axes.middleware.AxesMiddleware' to MIDDLEWARE     │
│       (must come after SessionMiddleware)                   │
│       python manage.py migrate                              │
│                                                             │
│  4. PIN UNPINNED PACKAGES — run:                            │
│       pip freeze > requirements.txt                         │
│     (after installing everything in a clean venv)           │
│                                                             │
│  5. PURGE COMMITTED FILES FROM GIT HISTORY:                 │
│       git rm --cached .DS_Store .coverage                   │
│       git commit -m "chore: remove stray OS/coverage files" │
│                                                             │
│  6. AFTER ALL CHANGES:                                      │
│       python manage.py migrate                              │
│       python manage.py collectstatic                        │
└─────────────────────────────────────────────────────────────┘
""")