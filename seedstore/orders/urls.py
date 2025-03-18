from django.urls import path
from .views import checkout, upi_payment, payment_success

urlpatterns = [
    path('checkout/', checkout, name='checkout'),
    path('upi-payment/', upi_payment, name='upi_payment'),
    path('payment-success/', payment_success, name='payment_success'),
]