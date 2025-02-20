from django.urls import path
from .views import signup

urlpatterns = [
    path('signup/', signup, name='signup'),
    # path('login/', user_login, name='login'),
    # path('logout/', user_logout, name='logout'),
    # path('auth/', login_or_register, name='auth'),  # Handles both login and register
]
