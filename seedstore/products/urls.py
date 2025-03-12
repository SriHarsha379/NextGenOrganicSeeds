from django.urls import path

from . import views
from .views import seed_list, wishlist, homepage, search_seeds

urlpatterns = [
    path('', seed_list, name='seed_list'),
    path('wishlist/', wishlist, name='wishlist'),
    path('homepage/', homepage, name='homepage'),
    path('seeds/native-vegetable-seeds/', views.native_vegetable_seeds, name='native_vegetable_seeds'),
    path('seeds/leafy-vegetable-seeds/', views.leafy_vegetable_seeds, name='leafy_vegetable_seeds'),
    path('seeds/exotic-vegetable-seeds/', views.exotic_vegetable_seeds, name='exotic_vegetable_seeds'),
    path('seeds/hybrid-vegetable-seeds/', views.hybrid_vegetable_seeds, name='hybrid_vegetable_seeds'),
    path('search/', search_seeds, name='search_seeds'),
    path('seeds/winter_flower_seeds/', views.winter_flower_seeds, name='winter_flower_seeds'),
    path('seeds/all_seasonal_flower_seeds/', views.all_seasonal_flower_seeds, name='all_seasonal_flower_seeds'),
    path('seeds/summer_flower_seeds/', views.summer_flower_seeds, name='summer_flower_seeds'),
]
