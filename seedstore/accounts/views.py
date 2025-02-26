from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.models import User
from django.contrib import messages


def user_login(request):
    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect("seed_list")  # Redirect to the seed list page
        else:
            messages.error(request, "Invalid username or password")

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
