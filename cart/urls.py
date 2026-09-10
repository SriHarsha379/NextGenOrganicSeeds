from django.urls import path, re_path

from . import views
from .views import (
    add_to_cart, view_cart, remove_from_cart, checkout,
    update_cart_quantity, process_order, clear_cart,
    get_cart, phonepe_webhook, order_success
)
from .views import get_phonepe_payment_status  # Make sure it's imported

urlpatterns = [
    path('add/<int:seed_id>/', add_to_cart, name='add_to_cart'),
    path('view/', view_cart, name='view_cart'),
    path('remove/<int:cart_id>/', remove_from_cart, name='remove_from_cart'),
    path('checkout/', checkout, name='checkout'),
    path('update/<int:item_id>/', update_cart_quantity, name='update_cart_quantity'),
    path('process_order/', process_order, name='process_order'),
    path("clear/", clear_cart, name="clear_cart"),
    path('get_cart/', get_cart, name='get_cart'),
    path('validate_coupon/', views.validate_coupon, name='validate_coupon'),
    path("order/success/<str:phonepe_order_id>/", views.order_success, name="order_success"),
    path('get-phonepe-payment-status/<str:order_id>/', get_phonepe_payment_status, name='get_phonepe_payment_status'),
    path("order/retry/<str:phonepe_order_id>/", views.retry_payment, name="retry_payment"),
]
