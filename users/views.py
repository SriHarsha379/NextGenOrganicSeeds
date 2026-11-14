from django.shortcuts import redirect


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

