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

print("\naccounts/models.py — revert CampaignSend.sent_at regression")
patch(
    "accounts/models.py",
    "Revert sent_at to auto_now=True (must update on each send, not freeze at creation)",
    "    sent_at = models.DateTimeField(auto_now_add=True)",
    "    sent_at = models.DateTimeField(auto_now=True)",
)

print("\nseedstore/urls.py — remove duplicate parse_raw_order_data at root")
patch(
    "seedstore/urls.py",
    "Remove root-level parse_raw_order_data (canonical URL lives in orders/urls.py)",
    "    path('parse-order-data/', parse_raw_order_data, name='parse_order_data'),\n",
    "",
)
patch(
    "seedstore/urls.py",
    "Remove now-unused parse_raw_order_data import",
    "from orders.views import parse_raw_order_data\n",
    "",
)

print("\naccounts/views.py — fix user enumeration in forgot_password")
patch(
    "accounts/views.py",
    "forgot_password: stop leaking whether email is registered",
    '''        except get_user_model().DoesNotExist:
            messages.error(request, "No account found with this email.")
            return redirect("forgot_password")''',
    '''        except get_user_model().DoesNotExist:
            # Don't reveal whether the email is registered — always show the same message.
            messages.success(request, "If an account with that email exists, a reset link has been sent.")
            return redirect("/accounts/password_reset_done/")''',
)

print("\naccounts/forms.py — fix user enumeration in ForgotPasswordForm")
patch(
    "accounts/forms.py",
    "ForgotPasswordForm: remove email-existence leak",
    '''    def clean_email(self):
        email = self.cleaned_data['email']
        if not User.objects.filter(email=email).exists():
            raise forms.ValidationError("No account found with this email.")
        return email''',
    '''    def clean_email(self):
        # Do not validate existence here — revealing whether an email is registered
        # allows enumeration. The view always shows the same success message.
        return self.cleaned_data['email']''',
)

print("\nsend_winback_emails.py — fix misleading 10% off subject line")
patch(
    "accounts/management/commands/send_winback_emails.py",
    "Remove false promise of 10% off from email subject",
    '                subject="We miss you at Hasa Farm \U0001f331 Here\'s 10% off your next order",',
    '                subject="We miss you at Hasa Farm \U0001f331 Come back and explore our seeds",',
)

print("\nusers/views.py — remove dead imports")
patch(
    "users/views.py",
    "Remove dead imports from commented-out signup view",
    """from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib import messages
from django.contrib.auth.models import User
from .forms import CustomUserCreationForm""",
    "from django.shortcuts import redirect",
)

print("\nDone.\n")
print("Manual steps:")
print("  1. Run: python3 manage.py makemigrations accounts --name revert_sent_at_to_auto_now")
print("     then: python3 manage.py migrate")
print("  2. Remove /accounts/forgot-password/ route and point all reset links")
print("     to /accounts/password-reset/ (Django built-in, enumeration-safe)")
print("  3. For the winback email: either create a real coupon via admin and")
print("     pass it in the email context, or leave the new neutral subject")
