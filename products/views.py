from django.shortcuts import render
from .models import Seed, Category
from cart.models import Cart  # Import the Cart model
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from .utils.phonepe_client import client
from urllib.parse import quote

SEED_REAL_IMAGE_FALLBACKS = {
    "celery": "https://loremflickr.com/600/400/celery,vegetable",
    "capsicum bell pepper": "https://loremflickr.com/600/400/bell-pepper,capsicum,vegetable",
    "pak choi": "https://loremflickr.com/600/400/pak-choi,bok-choy,vegetable",
    "curly kale": "https://loremflickr.com/600/400/curly-kale,vegetable",
    "broccoli": "https://loremflickr.com/600/400/broccoli,vegetable",
    "methi": "https://loremflickr.com/600/400/fenugreek,leafy,vegetable",
    "chukka kura": "https://loremflickr.com/600/400/sorrel,leafy,greens",
    "coriander": "https://loremflickr.com/600/400/coriander,cilantro,herb",
    "amaranth green(thotakura)": "https://loremflickr.com/600/400/amaranth,leafy,greens",
    "palak/spinach": "https://loremflickr.com/600/400/spinach,leafy,vegetable",
    "spinach": "https://loremflickr.com/600/400/spinach,leafy,vegetable",
    "radish": "https://loremflickr.com/600/400/radish,vegetable",
    "brinjal": "https://loremflickr.com/600/400/eggplant,brinjal,vegetable",
    "tomato": "https://loremflickr.com/600/400/tomato,vegetable",
    "ladies finger": "https://loremflickr.com/600/400/okra,lady-finger,vegetable",
    "papads": "https://loremflickr.com/600/400/papad,papadum,food",
}


def _resolve_seed_image_url(seed):
    if seed.image:
        try:
            return seed.image.url
        except ValueError:
            pass

    normalized_name = seed.name.strip().lower()
    if normalized_name in SEED_REAL_IMAGE_FALLBACKS:
        return SEED_REAL_IMAGE_FALLBACKS[normalized_name]

    query = quote(f"{seed.name},vegetable")
    return f"https://loremflickr.com/600/400/{query}"


def _attach_display_image_url(seeds):
    for seed in seeds:
        seed.display_image_url = _resolve_seed_image_url(seed)
    return seeds




def seed_list(request):
    categories = [
        ("Native Vegetable Seeds", "native_vegetable_seeds", "Native"),
        ("Leafy Vegetable Seeds", "leafy_vegetable_seeds", "Leafy"),
        ("Exotic Vegetable Seeds", "exotic_vegetable_seeds", "Exotic"),
        ("Winter Flower Seeds", "winter_flower_seeds", "Winter"),
        ("All Seasonal Flower Seeds", "all_seasonal_flower_seeds", "All seasonal"),
        ("Summer Flower Seeds", "summer_flower_seeds", "Summer"),
    ]

    category_data = []
    for title, url_name, category_name in categories:
        seeds = list(Seed.objects.filter(category__name__iexact=category_name).order_by('-id')[:4])
        _attach_display_image_url(seeds)
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
    seeds = list(Seed.objects.filter(category=category))
    _attach_display_image_url(seeds)

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


# Search stays separate:
def search_seeds(request):
    query = request.GET.get('q', '')
    results = list(Seed.objects.filter(name__icontains=query)) if query else []
    _attach_display_image_url(results)
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
