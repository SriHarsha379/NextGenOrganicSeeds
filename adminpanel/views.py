# adminpanel/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.shortcuts import redirect
from products.models import Seed, Category
from django.contrib.auth.decorators import login_required, user_passes_test



# ----- Dashboard -----
def admin_required(view_func):
    """
    Only allow superuser access to adminpanel views.
    Redirects non-admins to your custom login page.
    """
    return login_required(
        user_passes_test(lambda u: u.is_superuser, login_url='/accounts/login/')(view_func)
    )


@admin_required
def dashboard_view(request):
    total_seeds = Seed.objects.count()
    total_categories = Category.objects.count()
    low_stock = Seed.objects.filter(stock__lte=10).count()
    most_stocked = Seed.objects.order_by('-stock').first()
    recent_seeds = Seed.objects.order_by('-id')[:5]
    context = {
        'total_seeds': total_seeds,
        'total_categories': total_categories,
        'low_stock': low_stock,
        'most_stocked': most_stocked,
        'recent_seeds': recent_seeds
    }
    return render(request, 'adminpanel/dashboard.html', context)

# ----- Seed List -----
@admin_required
def seed_list(request):
    seeds = Seed.objects.all().order_by('-id')
    return render(request, 'adminpanel/seed_list.html', {'seeds': seeds})

# ----- Add Seed -----
@admin_required
def seed_add(request):
    categories = Category.objects.all()
    if request.method == 'POST':
        name = request.POST['name']
        description = request.POST['description']
        price = request.POST['price']
        stock = request.POST['stock']
        category_id = request.POST.get('category')
        image = request.FILES.get('image')
        category = Category.objects.get(id=category_id) if category_id else None

        Seed.objects.create(
            name=name,
            description=description,
            price=price,
            stock=stock,
            category=category,
            image=image
        )
        return redirect('adminpanel:seed_list')
    return render(request, 'adminpanel/seed_add.html', {'categories': categories})

# ----- Edit Seed -----
# Edit Seed
@admin_required
def seed_edit(request, id):
    seed = Seed.objects.get(id=id)
    categories = Category.objects.all()
    if request.method == 'POST':
        seed.name = request.POST['name']
        seed.description = request.POST['description']
        seed.price = request.POST['price']
        seed.stock = request.POST['stock']
        category_id = request.POST.get('category')
        seed.category = Category.objects.get(id=category_id) if category_id else None
        if request.FILES.get('image'):
            seed.image = request.FILES.get('image')
        seed.save()
        return redirect('adminpanel:seed_list')
    return render(request, 'adminpanel/seed_edit.html', {'seed': seed, 'categories': categories})

# ----- Delete Seed -----
@admin_required
def seed_delete(request, id):
    seed = get_object_or_404(Seed, id=id)
    seed.delete()
    return redirect('adminpanel:seed_list')


@admin_required
def admin_logout(request):
    logout(request)
    return redirect('accounts:login')  # replace with your login page URL name

from django.db.models import Q

@admin_required
def seed_inventory(request):
    seeds = Seed.objects.all().order_by('-id')

    # --- Search & Filters ---
    search_query = request.GET.get('q', '')
    category_id = request.GET.get('category', '')
    stock_filter = request.GET.get('stock', '')  # 'low', 'in', or '' for all

    if search_query:
        seeds = seeds.filter(name__icontains=search_query)

    if category_id:
        seeds = seeds.filter(category__id=category_id)

    if stock_filter == 'low':
        seeds = seeds.filter(stock__lte=10)
    elif stock_filter == 'in':
        seeds = seeds.filter(stock__gt=10)

    categories = Category.objects.all()
    total_seeds = seeds.count()
    low_stock_count = seeds.filter(stock__lte=10).count()
    recent_seeds = seeds[:5]

    context = {
        'seeds': seeds,
        'categories': categories,
        'search_query': search_query,
        'category_id': category_id,
        'stock_filter': stock_filter,
        'total_seeds': total_seeds,
        'low_stock_count': low_stock_count,
        'recent_seeds': recent_seeds,
    }
    return render(request, 'adminpanel/seed_inventory.html', context)