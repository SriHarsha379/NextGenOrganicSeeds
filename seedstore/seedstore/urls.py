from django.contrib import admin
from django.urls import path, include
from users.views import home_redirect  # Import the home redirect view
from cart.views import order_success

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home_redirect, name='home'),  # Redirect to seed list
    path('seeds/', include('products.urls')),  # Include seed URLs
    path('cart/', include('cart.urls')),  # Include cart URLs
    path('accounts/', include('accounts.urls')),
    path('order-success/', order_success, name='order_success'),
]

