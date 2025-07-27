from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from orders.views import parse_raw_order_data
from users.views import home_redirect
from cart.views import phonepe_webhook, order_success

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home_redirect, name='home'),
    path('seeds/', include('products.urls')),
    path('cart/', include('cart.urls')),
    path('accounts/', include('accounts.urls')),
    path('orders/', include('orders.urls')),

    path('parse-order-data/', parse_raw_order_data, name='parse_order_data'),
 # ✅ FIXED: success URL now works
    path('order/success/<str:phonepe_order_id>/', order_success, name='order_success'),

    # ✅ FIXED: webhook is directly mapped
    path('phonepe/webhook/', phonepe_webhook, name='phonepe_webhook'),
    # ✅ KEEP ONLY this version with trailing slash
    path('payment/response/', phonepe_webhook, name='phonepe_webhook'),
]

# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
