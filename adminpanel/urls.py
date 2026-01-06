from django.urls import path
from accounts.views import user_login
from . import views

app_name = 'adminpanel'

urlpatterns = [
    path('login/', user_login, name='login'),  # Reuse accounts login
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('logout/', views.admin_logout, name='logout'),
    path('seeds/', views.seed_list, name='seed_list'),
    path('seeds/add/', views.seed_add, name='seed_add'),
    path('seeds/<int:id>/edit/', views.seed_edit, name='seed_edit'),
    path('seeds/<int:id>/delete/', views.seed_delete, name='seed_delete'),
    path('inventory/', views.seed_inventory, name='seed_inventory'),
    path('orders/', views.order_list, name='order_list'),
    path('orders/<int:order_id>/', views.order_detail, name='order_detail'),
]
