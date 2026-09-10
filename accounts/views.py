from django.contrib.auth.decorators import user_passes_test
from django.utils.timezone import now
from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout, get_user_model
from django.contrib.auth.models import User
from django.contrib import messages
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.contrib.auth.tokens import default_token_generator
from django.conf import settings
import time
from django.core.mail import send_mail, BadHeaderError
from smtplib import SMTPException
from django.core.validators import validate_email
from django.core.exceptions import ValidationError


from orders.models import Order
from products.models import Seed
from .forms import ForgotPasswordForm, LoginForm


def user_login(request):
    if request.method == "POST":
        form = LoginForm(request, data=request.POST)

        if form.is_valid():
            username = form.cleaned_data.get("username").strip()
            password = form.cleaned_data.get("password")
            remember_me = form.cleaned_data.get("remember_me")

            # 🚫 Reject inputs starting with www.
            if username.lower().startswith("www."):
                messages.error(request, "Please enter a valid username or email without 'www.'")
                return render(request, "accounts/login.html", {"form": form})

            # Find user by username or email
            try:
                user_obj = User.objects.get(username=username)
            except User.DoesNotExist:
                try:
                    user_obj = User.objects.get(email__iexact=username)
                except User.DoesNotExist:
                    user_obj = None

            if user_obj:
                user = authenticate(request, username=user_obj.username, password=password)
                if user:
                    login(request, user)

                    # Session expiry
                    if remember_me:
                        request.session.set_expiry(1209600)  # 2 weeks
                    else:
                        request.session.set_expiry(3600)  # 1 hour

                    request.session.modified = True
                    print(f"✅ Login successful: {user.username}")
                    if user.is_superuser:
                        return redirect("adminpanel:dashboard")
                    return redirect("home")
                else:
                    messages.error(request, "Invalid password. Please try again.")
            else:
                messages.error(request, "Account does not exist. <a href='/register/'>Register here</a> or contact support.")
    else:
        form = LoginForm()

    return render(request, "accounts/login.html", {"form": form})


def user_register(request):
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "").strip()
        confirm_password = request.POST.get("confirm_password", "").strip()

        # 1. Check if passwords match
        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return redirect("register")

        # 2. Check if username exists
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
            return redirect("register")

        # 3. Check if email is already used
        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already registered.")
            return redirect("register")

        # 4. Validate email format only (no DNS/MX checks)
        try:
            validate_email(email)
        except ValidationError:
            messages.error(request, "Invalid email address format.")
            return redirect("register")

        # 5. Create the user
        user = User.objects.create_user(username=username, email=email, password=password)

        # 6. Optionally send welcome email
        try:
            send_welcome_email(user)
        except Exception as e:
            messages.warning(request, f"Registered, but email sending failed: {e}")

        # 7. Log the user in and redirect
        login(request, user)
        return redirect("seed_list")

    return render(request, "accounts/register.html")


def user_logout(request):
    logout(request)
    return redirect("seed_list")


class AutoLogout:
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

        return self.get_response(request)


# Forgot Password View (Step 1)
def forgot_password(request):
    if request.method == "POST":
        email = request.POST.get('email')
        try:
            user = get_user_model().objects.get(email=email)
            uid = urlsafe_base64_encode(str(user.pk).encode())  # Corrected line
            token = default_token_generator.make_token(user)

            # Get protocol and domain for the link
            protocol = 'https' if request.is_secure() else 'http'
            domain = request.get_host()

            reset_link = f"{protocol}://{domain}/accounts/reset-password/{uid}/{token}/"
            subject = "Password Reset Request - HASA Farm"
            message = render_to_string("accounts/password_reset_email.html", {
                'user': user,
                'reset_link': reset_link,
            })

            # Send email with HTML content
            send_mail(
                subject,
                message,  # plain-text message (not needed for HTML, but you can leave it empty)
                settings.EMAIL_HOST_USER,
                [email],
                html_message=message  # Add the HTML version of the message here
            )

            messages.success(request, "A password reset link has been sent to your email.")
            return redirect("/accounts/password_reset_done/")

        except get_user_model().DoesNotExist:
            messages.error(request, "No account found with this email.")
            return redirect("forgot_password")

    return render(request, "accounts/forgot_password.html")



# # Reset Password View (Step 2)
# def reset_password(request, uidb64, token):
#     try:
#         uid = urlsafe_base64_decode(uidb64).decode()
#         user = get_user_model().objects.get(pk=uid)
#     except (User.DoesNotExist, ValueError, TypeError):
#         user = None
#
#     if user and default_token_generator.check_token(user, token):
#         if request.method == "POST":
#             new_password = request.POST["password"]
#             confirm_password = request.POST["confirm_password"]
#             if new_password == confirm_password:
#                 user.set_password(new_password)
#                 user.save()
#                 messages.success(request, "Your password has been reset successfully. You can now log in.")
#                 return redirect("login")
#             else:
#                 messages.error(request, "Passwords do not match. Please try again.")
#
#         return render(request, "accounts/reset_password.html", {"valid": True})
#
#     else:
#         messages.error(request, "The password reset link is invalid or has expired.")
#         return render(request, "accounts/reset_password.html", {"valid": False})


def reset_password(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User.objects.get(pk=uid)
    except (User.DoesNotExist, ValueError, TypeError):
        user = None

    if user and default_token_generator.check_token(user, token):
        if request.method == "POST":
            new_password = request.POST["password"]
            confirm_password = request.POST["confirm_password"]

            if new_password == confirm_password:
                user.set_password(new_password)
                user.save()
                messages.success(request, "Your password has been reset successfully. You can now log in.")
                return redirect("login")
            else:
                messages.error(request, "Passwords do not match. Try again.")

        return render(request, "accounts/reset_password.html", {"valid": True})
    else:
        return render(request, "accounts/reset_password.html", {"valid": False})


def send_welcome_email(user, max_retries=3):
    subject = 'Welcome to Hasa Farm!'
    html_message = render_to_string('accounts/emails/welcome_email.html', {'user': user})
    plain_message = f"""Hi {user.username},

Thank you for registering at Hasa Farm!

We're excited to have you on board! 🌱

Feel free to explore our organic seed collection and start your gardening journey with us.

If you have any questions, just reply to this email — we're happy to help.

— HASA Farm Team
"""
    from_email = settings.DEFAULT_FROM_EMAIL
    to = user.email

    attempt = 0
    while attempt < max_retries:
        try:
            send_mail(
                subject,
                plain_message,
                from_email,
                [to],
                html_message=html_message
            )
            print(f"✅ Welcome email sent to {to}")
            break
        except (SMTPException, BadHeaderError) as e:
            attempt += 1
            print(f"❌ Error sending email to {to} (Attempt {attempt}/{max_retries}): {e}")
            time.sleep(2)  # wait before retrying
    else:
        print(f"🚨 Failed to send welcome email to {to} after {max_retries} attempts.")

def password_reset_done(request):
    return render(request, "accounts/password_reset_done.html")


# ─────────────────────────── Marketing email unsubscribe ──────────────────────
from django.core import signing
from .models import MarketingEmailPreference

UNSUBSCRIBE_SALT = "hasafarm-marketing-unsubscribe"


def make_unsubscribe_token(email):
    """Signed token so unsubscribe links can't be guessed/forged for other emails."""
    return signing.dumps({"email": email}, salt=UNSUBSCRIBE_SALT)


def unsubscribe(request, token):
    try:
        data = signing.loads(token, salt=UNSUBSCRIBE_SALT, max_age=60 * 60 * 24 * 90)  # 90-day link validity
        email = data["email"]
    except signing.BadSignature:
        return render(request, "accounts/unsubscribe_result.html", {"success": False}, status=400)

    pref, _ = MarketingEmailPreference.objects.get_or_create(email=email)
    pref.unsubscribed = True
    pref.unsubscribed_at = now()
    pref.save(update_fields=["unsubscribed", "unsubscribed_at"])

    return render(request, "accounts/unsubscribe_result.html", {"success": True, "email": email})