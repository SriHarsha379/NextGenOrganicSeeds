from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from orders.views import parse_raw_order_data
from users.views import home_redirect  # Import the home redirect view
from cart.views import order_success

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home_redirect, name='home'),  # Redirect to seed list
    path('seeds/', include('products.urls')),  # Include seed URLs
    path('cart/', include('cart.urls')),  # Include cart URLs
    path('accounts/', include('accounts.urls')),
    path('order-success/', order_success, name='order_success'),
    # project/urls.py
    path('orders/', include('orders.urls')),
path('parse-order-data/', parse_raw_order_data, name='parse_order_data'),

]

# ✅ Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)