from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from users.views import home_redirect  # Import the home redirect view
from cart.views import order_success, cashfree_webhook_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home_redirect, name='home'),  # Redirect to seed list
    path('seeds/', include('products.urls')),  # Include seed URLs
    path('cart/', include('cart.urls')),  # Include cart URLs
    path('accounts/', include('accounts.urls')),
    path('payment/confirmation/', order_success, name='order_success'),
path('payment/webhook/', cashfree_webhook_view, name='cashfree-webhook'),

]

# ✅ Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)