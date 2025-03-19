from django.shortcuts import render
from .models import Seed, Category
from cart.models import Cart  # Import the Cart model
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required


@login_required(login_url="/accounts/login/")
def seed_list(request):
    seeds = Seed.objects.all()
    cart = request.session.get("cart", {})  # Retrieve cart from session
    cart_count = len(cart)  # Count unique items in the cart

    context = {"seeds": seeds, "cart_count": cart_count}
    return render(request, "products/seed_list.html", context)


def homepage(request):
    bestselling_seeds = Seed.objects.order_by('-sold_count')[:8]  # Assuming 'sold_count' tracks bestsellers
    return render(request, 'products/seed_list.html', {'bestselling_seeds': bestselling_seeds})

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
    results = Seed.objects.filter(name__icontains=query) if query else []  # Case-insensitive search

    return render(request, 'products/search_results.html', {'results': results, 'query': query})

def winter_flower_seeds(request):
    category = get_object_or_404(Category, name="Native")  # Ensure capitalization matches DB
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
    category = get_object_or_404(Category, name="Native")  # Ensure capitalization matches DB
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
    category = get_object_or_404(Category, name="Native")  # Ensure capitalization matches DB
    seeds = Seed.objects.filter(category=category)

    # Get the cart from the session
    cart = request.session.get('cart', {})

    # Calculate the total unique items in the cart
    unique_item_count = len(cart)

    return render(request, 'products/summer_flower_seeds.html', {
        'seeds': seeds,
        'cart_count': unique_item_count,  # Pass cart count to template
    })
