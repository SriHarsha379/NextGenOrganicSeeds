from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib import messages
from django.contrib.auth.models import User
from .forms import CustomUserCreationForm


def signup(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = User.objects.create_user(
                username=form.cleaned_data['email'],  # Using email as username
                email=form.cleaned_data['email'],
                password=form.cleaned_data['password']
            )
            login(request, user)  # Auto-login after signup
            messages.success(request, 'Your account has been created successfully. You are now logged in.')
            return redirect('home')  # Redirect to home after registration
        else:
            messages.error(request, 'There was an error with your registration.')
    else:
        form = CustomUserCreationForm()

    return render(request, 'users/signup.html', {'form': form})

# def user_login(request):
#     if request.method == "POST":
#         form = AuthenticationForm(data=request.POST)
#         if form.is_valid():
#             user = form.get_user()
#             login(request, user)
#             return redirect('home')  # Redirect to home after login
#     else:
#         form = AuthenticationForm()
#     return render(request, 'users/login.html', {'form': form})


# def user_logout(request):
#     logout(request)
#     messages.info(request, 'You have been logged out.')
#     return redirect('home')  # Redirect to login after logout

def home_redirect(request):
    return redirect('seed_list')  # Redirect to seed list

def login_or_register(request):
    is_register = request.GET.get('register') == 'true'  # Check if the user wants to register

    if is_register:
        # Handle registration
        if request.method == 'POST':
            form = UserCreationForm(request.POST)
            if form.is_valid():
                form.save()  # Save the user to the database
                messages.success(request, 'Your account has been created successfully!')
                return redirect('login')  # Redirect to login after successful registration
        else:
            form = UserCreationForm()  # Show registration form
    else:
        # Handle login
        if request.method == 'POST':
            form = AuthenticationForm(data=request.POST)
            if form.is_valid():
                user = form.get_user()
                login(request, user)
                return redirect('home')  # Redirect to home after login
        else:
            form = AuthenticationForm()

    return render(request, 'users/auth.html', {'form': form, 'is_register': is_register})
