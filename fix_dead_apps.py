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

# ── 1. Move home_redirect to products/views.py (users app sole purpose) ──────
print("\nproducts/views.py — absorb home_redirect from users app")
patch(
    "products/views.py",
    "Add home_redirect so users app can be deleted",
    "from django.shortcuts import render",
    "from django.shortcuts import render, redirect\n\n\ndef home_redirect(request):\n    return redirect('seed_list')",
)

# ── 2. Update seedstore/urls.py to import from products instead of users ──────
print("\nseedstore/urls.py — point home_redirect import to products")
patch(
    "seedstore/urls.py",
    "home_redirect: import from products.views, not users.views",
    "from users.views import home_redirect",
    "from products.views import home_redirect",
)

# ── 3. Remove home and users from INSTALLED_APPS ──────────────────────────────
print("\nseedstore/settings.py — remove dead home and users apps")
patch(
    "seedstore/settings.py",
    "Remove dead 'users' app from INSTALLED_APPS",
    "    'users',\n",
    "",
)
patch(
    "seedstore/settings.py",
    "Remove dead 'home' app from INSTALLED_APPS",
    "    'home',\n",
    "",
)

# ── 4. logs directory placeholder ────────────────────────────────────────────
print("\nlogs/")
logs_dir = os.path.join(ROOT, "logs")
os.makedirs(logs_dir, exist_ok=True)
gitkeep = os.path.join(logs_dir, ".gitkeep")
if not os.path.exists(gitkeep):
    open(gitkeep, "w").close()
print("  OK  Created logs/.gitkeep")

# ── 5. .gitignore — ignore log files but keep the directory ──────────────────
print("\n.gitignore")
patch(
    ".gitignore",
    "Track logs dir but ignore log files",
    "# ======================\n# macOS / editor junk",
    "# ======================\n# Logs\n# ======================\nlogs/*.log\n\n# ======================\n# macOS / editor junk",
)

print("\nDone.\n")
print("Next steps:")
print("  1. Verify the site still starts:")
print("     python3 manage.py check")
print("")
print("  2. The users/ and home/ directories still exist on disk.")
print("     Safe to delete after confirming the app starts cleanly:")
print("     rm -rf users/ home/")
print("")
print("  3. Commit:")
print("     git add -A && git commit -m 'chore: remove dead home/users apps, add log dir'")
