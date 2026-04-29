from django.contrib import admin
from django.urls import path, include

from cart.views import order_success, phonepe_webhook
from orders.views import parse_raw_order_data
from users.views import home_redirect

# 👇 ADD THESE TWO IMPORTS
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', home_redirect, name='home'),

    # Built-in Django admin
    path('django-admin/', admin.site.urls),

    # Custom admin panel
    path('admin/', include('adminpanel.urls')),

    # Other apps
    path('seeds/', include('products.urls')),
    path('cart/', include('cart.urls')),
    path('accounts/', include('accounts.urls')),
    path('orders/', include('orders.urls')),

    # Misc endpoints
    path('parse-order-data/', parse_raw_order_data, name='parse_order_data'),
    path('order/success/<str:phonepe_order_id>/', order_success, name='order_success'),
    path('phonepe/webhook/', phonepe_webhook, name='phonepe_webhook'),
    path('payment/response/', phonepe_webhook, name='phonepe_payment_response'),
]

# 👇 ADD THIS BLOCK AT THE VERY BOTTOM
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)