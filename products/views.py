from django.shortcuts import render
from .models import Seed, Category
from cart.models import Cart  # Import the Cart model
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from .utils.phonepe_client import client




def seed_list(request):
    categories = [
        ("Native Vegetable Seeds", "native_vegetable_seeds", "Native"),
        ("Leafy Vegetable Seeds", "leafy_vegetable_seeds", "Leafy"),
        ("Exotic Vegetable Seeds", "exotic_vegetable_seeds", "Exotic"),
        ("Winter Flower Seeds", "winter_flower_seeds", "Winter"),
        ("All Seasonal Flower Seeds", "all_seasonal_flower_seeds", "All seasonal"),
        ("Summer Flower Seeds", "summer_flower_seeds", "Summer"),
        ("Food Products", "food_products", "Food"),
    ]

    category_data = []
    for title, url_name, category_name in categories:
        seeds = Seed.objects.filter(category__name__iexact=category_name).order_by('-id')[:4]
        category_data.append({
            "title": title,
            "url_name": url_name,
            "seeds": seeds
        })

    cart_count = len(request.session.get("cart", {}))

    response = render(request, "products/seed_list.html", {
        "category_data": category_data,
        "cart_count": cart_count
    })
    response["Cache-Control"] = "no-store, no-cache, must-revalidate, proxy-revalidate"
    response["Pragma"] = "no-cache"
    response["Expires"] = "0"
    return response



# def homepage(request):
#     categories = [
#         ("Native Vegetable Seeds", "native_vegetable_seeds", "Native"),
#         ("Leafy Vegetable Seeds", "leafy_vegetable_seeds", "Leafy"),
#         ("Exotic Vegetable Seeds", "exotic_vegetable_seeds", "Exotic"),
#         ("Winter Flower Seeds", "winter_flower_seeds", "Winter"),
#         ("All Seasonal Flower Seeds", "all_seasonal_flower_seeds", "All seasonal"),
#         ("Summer Flower Seeds", "summer_flower_seeds", "Summer"),
#     ]
#
#     category_data = []
#     for title, url_name, category_name in categories:
#         seeds = Seed.objects.filter(category__name__iexact=category_name).order_by('-id')[:4]
#         category_data.append({
#             "title": title,
#             "url_name": url_name,
#             "seeds": seeds
#         })
#
#     cart = request.session.get("cart", {})
#     cart_count = len(cart)
#
#     return render(request, "products/seed_list.html", {
#         "category_data": category_data,
#         "cart_count": cart_count
#     })

def wishlist(request):
    return render(request, 'wishlist.html')

def render_seeds_by_category(request, category_name, template_name):
    category = get_object_or_404(Category, name=category_name)
    seeds = Seed.objects.filter(category=category)

    cart = request.session.get('cart', {})
    unique_item_count = len(cart)

    return render(request, template_name, {
        'seeds': seeds,
        'cart_count': unique_item_count,
    })


# Now your views become just one-liners:
def native_vegetable_seeds(request):
    return render_seeds_by_category(request, "Native", 'products/native_vegetable_seeds.html')

def leafy_vegetable_seeds(request):
    return render_seeds_by_category(request, "Leafy", 'products/leafy-vegetable-seeds.html')

def exotic_vegetable_seeds(request):
    return render_seeds_by_category(request, "Exotic", 'products/exotic-vegetable-seeds.html')

def hybrid_vegetable_seeds(request):
    return render_seeds_by_category(request, "Hybrid", 'products/hybrid-vegetable-seeds.html')

def winter_flower_seeds(request):
    return render_seeds_by_category(request, "Winter", 'products/winter_flower_seeds.html')

def all_seasonal_flower_seeds(request):
    return render_seeds_by_category(request, "All seasonal", 'products/all_seasonal_flower_seeds.html')

def summer_flower_seeds(request):
    return render_seeds_by_category(request, "Summer", 'products/summer_flower_seeds.html')

def farm_crops(request):
    return render_seeds_by_category(request, "Farmcrops", 'products/farm_crops.html')

def food_products(request):
    return render_seeds_by_category(request, "Food", 'products/food_products.html')


# Search stays separate:
def search_seeds(request):
    query = request.GET.get('q', '')
    results = Seed.objects.filter(name__icontains=query) if query else Seed.objects.none()
    return render(request, 'products/search_results.html', {
        'results': results,
        'query': query
    })

# def farm_crops(request):
#     return render(request, 'products/farm_crops.html')

def privacy_policy(request):
    return render(request, 'products/privacy_policy.html')

def terms_conditions(request):
    return render(request, 'products/terms_conditions.html')

def disclaimer(request):
    return render(request, 'products/disclaimer.html')

def refund(request):
    return render(request, 'products/refund.html')

def shipping(request):
    return render(request, 'products/shipping.html')
