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

print("\nseedstore/settings.py")

# Fix CSRF_TRUSTED_ORIGINS — add hasaorganicseeds.com
patch(
    "seedstore/settings.py",
    "Add hasaorganicseeds.com to CSRF_TRUSTED_ORIGINS",
    '''CSRF_TRUSTED_ORIGINS = [
    "https://hasafarm.com",
    "https://www.hasafarm.com",
    "https://147.93.28.237",
]''',
    '''CSRF_TRUSTED_ORIGINS = [
    "https://hasafarm.com",
    "https://www.hasafarm.com",
    "https://hasaorganicseeds.com",
    "https://www.hasaorganicseeds.com",
    "https://147.93.28.237",
]''',
)

# Fix TIME_ZONE
patch(
    "seedstore/settings.py",
    "TIME_ZONE: UTC -> Asia/Kolkata",
    "TIME_ZONE = 'UTC'",
    "TIME_ZONE = 'Asia/Kolkata'",
)

# Fix SESSION_SAVE_EVERY_REQUEST
patch(
    "seedstore/settings.py",
    "SESSION_SAVE_EVERY_REQUEST: True -> False",
    "SESSION_SAVE_EVERY_REQUEST = True",
    "SESSION_SAVE_EVERY_REQUEST = False",
)

# Fix SESSION_EXPIRE_AT_BROWSER_CLOSE
patch(
    "seedstore/settings.py",
    "SESSION_EXPIRE_AT_BROWSER_CLOSE: False -> True",
    "SESSION_EXPIRE_AT_BROWSER_CLOSE = False",
    "SESSION_EXPIRE_AT_BROWSER_CLOSE = True",
)

# Fix SECURE_HSTS_PRELOAD — make it opt-in via env, not automatic
patch(
    "seedstore/settings.py",
    "SECURE_HSTS_PRELOAD: make it opt-in, not automatic",
    "SECURE_HSTS_PRELOAD = not DEBUG",
    "SECURE_HSTS_PRELOAD = config('HSTS_PRELOAD', default=False, cast=bool)  # opt-in only",
)

# Wire up Sentry (uses DSN from .env; no-ops gracefully if DSN not set)
patch(
    "seedstore/settings.py",
    "Wire up Sentry error tracking",
    "import os\nfrom pathlib import Path\n\nfrom decouple import config",
    '''import os
from pathlib import Path

from decouple import config

# ── Sentry error tracking (no-op if SENTRY_DSN is not set) ──────────────────
_sentry_dsn = config("SENTRY_DSN", default="")
if _sentry_dsn:
    import sentry_sdk
    sentry_sdk.init(
        dsn=_sentry_dsn,
        traces_sample_rate=0.1,   # 10% of transactions for performance monitoring
        send_default_pii=False,   # never send user PII to Sentry
    )''',
)

# Add file logging alongside console
patch(
    "seedstore/settings.py",
    "Add rotating file handler to LOGGING",
    '''    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },''',
    '''    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(BASE_DIR, "logs", "django.log"),
            "maxBytes": 5 * 1024 * 1024,  # 5 MB
            "backupCount": 5,
            "formatter": "verbose",
        },
    },''',
)

patch(
    "seedstore/settings.py",
    "Route root logger to both console and file",
    '''    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },''',
    '''    "root": {
        "handlers": ["console", "file"],
        "level": "WARNING",
    },''',
)

patch(
    "seedstore/settings.py",
    "Route cart/orders loggers to file too",
    '''        "cart": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "orders": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },''',
    '''        "cart": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
        "orders": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console", "file"],
            "level": "ERROR",
            "propagate": False,
        },''',
)

print("\nrequirements.txt — remove dead sentry-sdk stub (now properly wired)")
# sentry-sdk is now used — keep it but remove the unpinned comment block stub
patch(
    "requirements.txt",
    "Pin sentry-sdk in the main block, remove it from unpinned section",
    "# A+ upgrades\nsentry-sdk\ndj-database-url\npsycopg2-binary\ncelery\nredis\ndjango-celery-results",
    "# A+ upgrades (pin these after: pip install <pkg> && pip freeze | grep <pkg>)\ndj-database-url\npsycopg2-binary\ncelery\nredis\ndjango-celery-results\nsentry-sdk",
)

print("\nDone.\n")
print("Manual steps:")
print("  1. Create the logs directory:")
print("     mkdir -p logs && echo '*.log' >> .gitignore")
print("")
print("  2. Add SENTRY_DSN to .env (get it from sentry.io):")
print("     SENTRY_DSN=https://xxxx@oyyy.ingest.sentry.io/zzzz")
print("     (leave blank to disable — Sentry is a no-op without it)")
print("")
print("  3. Add HSTS_PRELOAD=True to .env only when you are sure")
print("     your domain will always serve HTTPS (irreversible).")
print("")
print("  4. Remove dead home/users apps from INSTALLED_APPS manually")
print("     (needs careful check that no templates/signals depend on them first)")
