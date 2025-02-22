from django.shortcuts import render
from .models import Seed, Category
from cart.models import Cart  # Import the Cart model
from django.shortcuts import render, get_object_or_404


def seed_list(request):
    seeds = Seed.objects.all()

    context = {
        'seeds': seeds,
    }
    return render(request, 'products/seed_list.html', context)


def homepage(request):
    bestselling_seeds = Seed.objects.order_by('-sold_count')[:8]  # Assuming 'sold_count' tracks bestsellers
    return render(request, 'products/seed_list.html', {'bestselling_seeds': bestselling_seeds})

def wishlist(request):
    return render(request, 'wishlist.html')

def native_vegetable_seeds(request):
    category = get_object_or_404(Category, name="Native")  # Ensure capitalization matches DB
    seeds = Seed.objects.filter(category=category)
    return render(request, 'products/native_vegetable_seeds.html', {'seeds': seeds})


def leafy_vegetable_seeds(request):
    category = get_object_or_404(Category, name="Leafy")
    seeds = Seed.objects.filter(category=category)
    return render(request, 'products/leafy-vegetable-seeds.html', {'seeds': seeds})

def exotic_vegetable_seeds(request):
    category = get_object_or_404(Category, name="Exotic")
    seeds = Seed.objects.filter(category=category)
    return render(request, 'products/exotic-vegetable-seeds.html', {'seeds': seeds})

def hybrid_vegetable_seeds(request):
    category = get_object_or_404(Category, name="Hybrid")
    seeds = Seed.objects.filter(category=category)
    return render(request, 'products/hybrid-vegetable-seeds.html', {'seeds': seeds})

def search_seeds(request):
    query = request.GET.get('q', '')  # Get the search query
    results = Seed.objects.filter(name__icontains=query) if query else []  # Case-insensitive search

    return render(request, 'products/search_results.html', {'results': results, 'query': query})
