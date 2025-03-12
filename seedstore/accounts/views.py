from django.utils.timezone import now
from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.models import User
from django.contrib import messages


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
            user = User.objects.create_user(username=username, email=email, password=password)
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
