from django.urls import path

from . import views
from .views import seed_list, wishlist, search_seeds, privacy_policy, terms_conditions, disclaimer, refund, \
    shipping, farm_crops

urlpatterns = [
    # path('', homepage, name='homepage'),  # ✅ Make homepage default
    path('', seed_list, name='seed_list'),
    path('wishlist/', wishlist, name='wishlist'),
    path('native-vegetable-seeds/', views.native_vegetable_seeds, name='native_vegetable_seeds'),
    path('leafy-vegetable-seeds/', views.leafy_vegetable_seeds, name='leafy_vegetable_seeds'),
    path('exotic-vegetable-seeds/', views.exotic_vegetable_seeds, name='exotic_vegetable_seeds'),
    path('hybrid-vegetable-seeds/', views.hybrid_vegetable_seeds, name='hybrid_vegetable_seeds'),
    path('search/', search_seeds, name='search_seeds'),
    path('winter_flower_seeds/', views.winter_flower_seeds, name='winter_flower_seeds'),
    path('all_seasonal_flower_seeds/', views.all_seasonal_flower_seeds, name='all_seasonal_flower_seeds'),
    path('summer_flower_seeds/', views.summer_flower_seeds, name='summer_flower_seeds'),
    path('farm_crops/', farm_crops, name='farm_crops'),
    path('privacy-policy/', privacy_policy, name='privacy_policy'),
    path('terms-conditions/', terms_conditions, name='terms_conditions'),
    path('disclaimer/', disclaimer, name='disclaimer'),
    path('refund/', refund, name='refund'),
    path('shipping/', shipping, name='shipping'),
]

