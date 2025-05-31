from django.urls import path
from .views import  upi_payment, payment_success, my_orders
from . import views


urlpatterns = [
    # path('checkout/', checkout, name='checkout'),
    path('upi-payment/', upi_payment, name='upi_payment'),
    path('payment-success/', payment_success, name='payment_success'),
    path('my-orders/', my_orders, name='my_orders'),
    path('orders/invoice/<int:order_id>/', views.download_invoice, name='download_invoice'),
    path('reorder/<int:order_id>/', views.reorder, name='reorder'),
]