from django.contrib import admin
from django.urls import path, include
from users.views import home_redirect  # Import the home redirect view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home_redirect, name='home'),  # Redirect to seed list
    path('seeds/', include('products.urls')),  # Include seed URLs
    path('cart/', include('cart.urls')),  # Include cart URLs
    path('users/', include('users.urls')),  # Include user authentication URLs
]
