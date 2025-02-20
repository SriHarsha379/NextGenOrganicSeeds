from django.urls import path
from .views import add_to_cart, view_cart, remove_from_cart, checkout, update_cart_quantity, \
    process_order  # Import checkout

urlpatterns = [
    path('add/<int:seed_id>/', add_to_cart, name='add_to_cart'),
    path('view/', view_cart, name='view_cart'),
    path('remove/<int:cart_id>/', remove_from_cart, name='remove_from_cart'),
    path('checkout/', checkout, name='checkout'),  # ✅ Add this line
    path('update/<int:item_id>/', update_cart_quantity, name='update_cart_quantity'),
    path("process_order/", process_order, name="process_order"),
]
