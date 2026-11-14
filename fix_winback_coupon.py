import os
ROOT = os.path.dirname(os.path.abspath(__file__))

def patch(path, label, old, new):
    full = os.path.join(ROOT, path)
    txt = open(full, encoding="utf-8").read()
    if old not in txt:
        print(f"  SKIP (pattern missing): {label}"); return
    open(full, "w", encoding="utf-8").write(txt.replace(old, new, 1))
    print(f"  OK  {label}")

print("\naccounts/management/commands/send_winback_emails.py")

# Add coupon import
patch(
    "accounts/management/commands/send_winback_emails.py",
    "Add Coupon import",
    "from orders.models import Order",
    "from orders.models import Order, Coupon",
)

# Add --coupon argument
patch(
    "accounts/management/commands/send_winback_emails.py",
    "Add --coupon CLI argument",
    '        parser.add_argument(\n            "--dry-run", action="store_true",',
    '        parser.add_argument(\n            "--coupon", type=str, default=None,\n            help="Optional coupon code to include in the email (must already exist in DB).",\n        )\n        parser.add_argument(\n            "--dry-run", action="store_true",',
)

# Pass coupon into handle
patch(
    "accounts/management/commands/send_winback_emails.py",
    "Read coupon from options in handle()",
    "        days = options[\"days\"]\n        cooldown_days = options[\"cooldown\"]\n        limit = options[\"limit\"]\n        dry_run = options[\"dry_run\"]",
    "        days = options[\"days\"]\n        cooldown_days = options[\"cooldown\"]\n        limit = options[\"limit\"]\n        dry_run = options[\"dry_run\"]\n        coupon_code = (options.get(\"coupon\") or \"\").strip().upper() or None\n\n        if coupon_code:\n            if not Coupon.objects.filter(code=coupon_code, active=True).exists():\n                self.stderr.write(self.style.ERROR(f\"Coupon '{coupon_code}' not found or inactive. Aborting.\"))\n                return\n            self.stdout.write(f\"Using coupon: {coupon_code}\")",
)

# Pass coupon to _send_winback_email calls
patch(
    "accounts/management/commands/send_winback_emails.py",
    "Pass coupon_code to _send_winback_email",
    "            self._send_winback_email(order, pref)\n            sent_count += 1",
    "            self._send_winback_email(order, pref, coupon_code=coupon_code)\n            sent_count += 1",
)

# Update dry-run log to show coupon
patch(
    "accounts/management/commands/send_winback_emails.py",
    "Show coupon in dry-run output",
    "                self.stdout.write(f\"  [DRY RUN] would email {email} (last order {order.created_at:%Y-%m-%d})\")",
    "                self.stdout.write(f\"  [DRY RUN] would email {email} (last order {order.created_at:%Y-%m-%d}) coupon={coupon_code or 'none'}\")",
)

# Update _send_winback_email signature and context
patch(
    "accounts/management/commands/send_winback_emails.py",
    "Accept and pass coupon_code in _send_winback_email",
    "    def _send_winback_email(self, order, pref):\n        email = pref.email\n        token = make_unsubscribe_token(email)\n        context = {\n            \"name\": order.full_name.split(\" \")[0] if order.full_name else \"there\",\n            \"shop_url\": f\"{settings.SITE_URL}/seeds/\",\n            \"unsubscribe_url\": f\"{settings.SITE_URL}/accounts/unsubscribe/{token}/\",\n        }",
    "    def _send_winback_email(self, order, pref, coupon_code=None):\n        email = pref.email\n        token = make_unsubscribe_token(email)\n        context = {\n            \"name\": order.full_name.split(\" \")[0] if order.full_name else \"there\",\n            \"shop_url\": f\"{settings.SITE_URL}/seeds/\",\n            \"unsubscribe_url\": f\"{settings.SITE_URL}/accounts/unsubscribe/{token}/\",\n            \"coupon_code\": coupon_code,\n        }",
)

# Fix subject to only mention discount when coupon is actually provided
patch(
    "accounts/management/commands/send_winback_emails.py",
    "Dynamic subject based on whether coupon is provided",
    '                subject="We miss you at Hasa Farm \U0001f331 Come back and explore our seeds",',
    '                subject=(\n                    f"We miss you at Hasa Farm \U0001f331 Here\'s {coupon_code} — a special offer for you"\n                    if coupon_code else\n                    "We miss you at Hasa Farm \U0001f331 Come back and explore our seeds"\n                ),',
)

print("\nDone.")
print("\nUsage:")
print("  # Dry run with a coupon:")
print("  python3 manage.py send_winback_emails --coupon COMEBACK10 --dry-run")
print("  # Live run:")
print("  python3 manage.py send_winback_emails --coupon COMEBACK10")
print("  # Without coupon (neutral email):")
print("  python3 manage.py send_winback_emails")
print("\nCreate the coupon first via /admin/dashboard/ before running live.")
