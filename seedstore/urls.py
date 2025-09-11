from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic.base import RedirectView

from orders.views import parse_raw_order_data
from users.views import home_redirect
from cart.views import phonepe_webhook, order_success

urlpatterns = [
    # Home page
    path('', home_redirect, name='home'),

    # Custom admin panel at /admin/
    path('admin/', include('adminpanel.urls')),  # All admin URLs under /admin/

    # Optional: redirect old /admin/login/ if anything still points to it
    path('admin/login/', RedirectView.as_view(url='/admin/login/')),

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

# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
