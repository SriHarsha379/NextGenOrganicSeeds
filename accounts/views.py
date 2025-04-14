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
from .forms import ForgotPasswordForm


def user_login(request):
    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]
        remember_me = request.POST.get("remember_me")

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)

            if remember_me:
                request.session.set_expiry(1209600)  # 2 weeks
            else:
                request.session.set_expiry(3600)  # 1 hour

            request.session.modified = True  # Ensure session updates
            print(f"✅ Login successful: {user.username}, Session Key: {request.session.session_key}")
            print(f"Session Data: {request.session.items()}")  # Debugging session content
            return redirect("home")
        else:
            messages.error(request, "Invalid username or password.")
            print("❌ Login failed")

    return render(request, "accounts/login.html")



def user_register(request):
    if request.method == "POST":
        username = request.POST["username"]
        email = request.POST["email"]
        password = request.POST["password"]

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists")
        else:
            # Create the user
            user = User.objects.create_user(username=username, email=email, password=password)

            # Send the welcome email
            send_welcome_email(user)

            # Log the user in immediately
            login(request, user)

            # Redirect to seed list page after successful registration
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
            subject = "Password Reset Request - HASA Organic Seeds"
            message = render_to_string("accounts/password_reset_email.html", {
                'user': user,
                'reset_link': reset_link,
            })
            send_mail(subject, message, settings.EMAIL_HOST_USER, [email])

            messages.success(request, "A password reset link has been sent to your email.")
            return redirect("/accounts/password_reset_done/")


        except get_user_model().DoesNotExist:
            messages.error(request, "No account found with this email.")
            return redirect("forgot_password")
    return render(request, "accounts/forgot_password.html")



# Reset Password View (Step 2)
def reset_password(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = get_user_model().objects.get(pk=uid)
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
                messages.error(request, "Passwords do not match. Please try again.")

        return render(request, "accounts/reset_password.html", {"valid": True})

    else:
        messages.error(request, "The password reset link is invalid or has expired.")
        return render(request, "accounts/reset_password.html", {"valid": False})


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


def send_welcome_email(user):
    subject = 'Welcome to Hasa Organic Seeds!'
    html_message = render_to_string('emails/welcome_email.html', {'user': user})
    plain_message = f"Hi {user.username},\n\nThank you for registering at Hasa Organic Seeds!"
    from_email = settings.DEFAULT_FROM_EMAIL
    to = user.email

    send_mail(subject, plain_message, from_email, [to], html_message=html_message)

def password_reset_done(request):
    return render(request, "accounts/password_reset_done.html")