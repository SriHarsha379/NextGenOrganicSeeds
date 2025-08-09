from django.shortcuts import render
from .models import Seed, Category
from cart.models import Cart  # Import the Cart model
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from .utils.phonepe_client import client




def seed_list(request):
    seeds = Seed.objects.all().order_by('id')

    cart = request.session.get("cart", {})  # Retrieve cart from session
    cart_count = len(cart)  # Count unique items in the cart

    # Disable cache for this page
    response = render(request, "products/seed_list.html", {"seeds": seeds, "cart_count": cart_count})
    response["Cache-Control"] = "no-store, no-cache, must-revalidate, proxy-revalidate"
    response["Pragma"] = "no-cache"
    response["Expires"] = "0"

    return response


def homepage(request):
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
        seeds = Seed.objects.filter(category__name=category_name).order_by('-id')[:4]
        category_data.append({
            "title": title,
            "url_name": url_name,
            "seeds": seeds
        })

    cart = request.session.get("cart", {})
    cart_count = len(cart)

    return render(request, "products/home.html", {
        "category_data": category_data,
        "cart_count": cart_count
    })


def wishlist(request):
    return render(request, 'wishlist.html')

def native_vegetable_seeds(request):
    category = get_object_or_404(Category, name="Native")  # Ensure capitalization matches DB
    seeds = Seed.objects.filter(category=category)

    # Get the cart from the session
    cart = request.session.get('cart', {})

    # Calculate the total unique items in the cart
    unique_item_count = len(cart)

    return render(request, 'products/native_vegetable_seeds.html', {
        'seeds': seeds,
        'cart_count': unique_item_count,  # Pass cart count to template
    })


def leafy_vegetable_seeds(request):
    category = get_object_or_404(Category, name="Leafy")
    seeds = Seed.objects.filter(category=category)

    # Get the cart from the session
    cart = request.session.get('cart', {})

    # Calculate the total unique items in the cart
    unique_item_count = len(cart)

    return render(request, 'products/leafy-vegetable-seeds.html', {
        'seeds': seeds,
        'cart_count': unique_item_count,  # Pass cart count to template
    })

def exotic_vegetable_seeds(request):
    category = get_object_or_404(Category, name="Exotic")
    seeds = Seed.objects.filter(category=category)

    # Get the cart from the session
    cart = request.session.get('cart', {})

    # Calculate the total unique items in the cart
    unique_item_count = len(cart)

    return render(request, 'products/exotic-vegetable-seeds.html', {
        'seeds': seeds,
        'cart_count': unique_item_count,  # Pass cart count to template
    })

def hybrid_vegetable_seeds(request):
    category = get_object_or_404(Category, name="Hybrid")
    seeds = Seed.objects.filter(category=category)

    # Get the cart from the session
    cart = request.session.get('cart', {})

    # Calculate the total unique items in the cart
    unique_item_count = len(cart)

    return render(request, 'products/hybrid-vegetable-seeds.html', {
        'seeds': seeds,
        'cart_count': unique_item_count,  # Pass cart count to template
    })


def search_seeds(request):
    query = request.GET.get('q', '')  # Get the search query
    if query:
        results = Seed.objects.filter(name__icontains=query)
    else:
        results = Seed.objects.none()
    return render(request, 'products/search_results.html', {'results': results, 'query': query})


def winter_flower_seeds(request):
    category = get_object_or_404(Category, name="Winter")  # Ensure capitalization matches DB
    seeds = Seed.objects.filter(category=category)

    # Get the cart from the session
    cart = request.session.get('cart', {})

    # Calculate the total unique items in the cart
    unique_item_count = len(cart)

    return render(request, 'products/winter_flower_seeds.html', {
        'seeds': seeds,
        'cart_count': unique_item_count,  # Pass cart count to template
    })

def all_seasonal_flower_seeds(request):
    category = get_object_or_404(Category, name="All seasonal")  # Ensure capitalization matches DB
    seeds = Seed.objects.filter(category=category)

    # Get the cart from the session
    cart = request.session.get('cart', {})

    # Calculate the total unique items in the cart
    unique_item_count = len(cart)

    return render(request, 'products/all_seasonal_flower_seeds.html', {
        'seeds': seeds,
        'cart_count': unique_item_count,  # Pass cart count to template
    })

def summer_flower_seeds(request):
    category = get_object_or_404(Category, name="Summer")  # Ensure capitalization matches DB
    seeds = Seed.objects.filter(category=category)

    # Get the cart from the session
    cart = request.session.get('cart', {})

    # Calculate the total unique items in the cart
    unique_item_count = len(cart)

    return render(request, 'products/summer_flower_seeds.html', {
        'seeds': seeds,
        'cart_count': unique_item_count,  # Pass cart count to template
    })

def farm_crops(request):
    category = get_object_or_404(Category, name="Farmcrops")  # Ensure capitalization matches DB
    seeds = Seed.objects.filter(category=category)

    # Get the cart from the session
    cart = request.session.get('cart', {})

    # Calculate the total unique items in the cart
    unique_item_count = len(cart)

    return render(request, 'products/farm_crops.html', {
        'seeds': seeds,
        'cart_count': unique_item_count,  # Pass cart count to template
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
