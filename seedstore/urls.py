from django.contrib import admin  # <-- import this
from django.urls import path, include

from cart.views import order_success, phonepe_webhook
from orders.views import parse_raw_order_data
from users.views import home_redirect

urlpatterns = [
    path('', home_redirect, name='home'),

    # Built-in Django admin
    path('django-admin/', admin.site.urls),   # keeps namespace 'admin'

    # Custom admin panel
    path('admin/', include('adminpanel.urls')),  # your custom panel

    # Other apps
    path('seeds/', include('products.urls')),
    path('cart/', include('cart.urls')),
    path('accounts/', include('accounts.urls')),
    path('orders/', include('orders.urls')),

    # Misc endpoints
    path('parse-order-data/', parse_raw_order_data, name='parse_order_data'),
    path('order/success/<str:phonepe_order_id>/', order_success, name='order_success'),
    path('phonepe/webhook/', phonepe_webhook, name='phonepe_webhook'),
    path('payment/response/', phonepe_webhook, name='phonepe_webhook'),
]
