from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib import messages
from django.contrib.auth.models import User
from .forms import CustomUserCreationForm


# def signup(request):
#     if request.method == 'POST':
#         form = CustomUserCreationForm(request.POST)
#         if form.is_valid():
#             user = User.objects.create_user(
#                 username=form.cleaned_data['email'],  # Using email as username
#                 email=form.cleaned_data['email'],
#                 password=form.cleaned_data['password']
#             )
#             login(request, user)  # Auto-login after signup
#             messages.success(request, 'Your account has been created successfully. You are now logged in.')
#             return redirect('home')  # Redirect to home after registration
#         else:
#             messages.error(request, 'There was an error with your registration.')
#     else:
#         form = CustomUserCreationForm()
#
#     return render(request, 'users/signup.html', {'form': form})


def home_redirect(request):
    return redirect('seed_list')  # Redirect to seed list

