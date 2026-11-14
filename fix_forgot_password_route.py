import os
ROOT = os.path.dirname(os.path.abspath(__file__))

def patch(path, label, old, new):
    full = os.path.join(ROOT, path)
    txt = open(full, encoding="utf-8").read()
    if old not in txt:
        print(f"  SKIP (pattern missing): {label}"); return
    open(full, "w", encoding="utf-8").write(txt.replace(old, new, 1))
    print(f"  OK  {label}")

print("\naccounts/urls.py")

# Remove custom forgot-password route (has enumeration leak, replaced by Django built-in)
patch(
    "accounts/urls.py",
    "Remove custom forgot-password route",
    "    path('forgot-password/', forgot_password, name='forgot_password'),\n",
    "",
)

# Remove now-unused imports
patch(
    "accounts/urls.py",
    "Remove forgot_password from imports",
    "from .views import user_login, user_register, user_logout, forgot_password, reset_password\n",
    "from .views import user_login, user_register, user_logout, reset_password\n",
)

# Point Django's built-in reset view at a named template dir it can find
# and give it the name 'forgot_password' so existing template links don't break
patch(
    "accounts/urls.py",
    "Alias password-reset as forgot_password so old links still work",
    "    path('password-reset/', auth_views.PasswordResetView.as_view(), name='password_reset'),",
    "    path('password-reset/', auth_views.PasswordResetView.as_view(), name='password_reset'),\n    path('forgot-password/', auth_views.PasswordResetView.as_view(), name='forgot_password'),  # alias — old links still work",
)

print("\nDone.")
