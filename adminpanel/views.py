# adminpanel/views.py
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
import csv

from orders.models import Order
from products.models import Category, Seed



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

from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum

@admin_required
def order_list(request):
    orders = Order.objects.all().order_by('-created_at')

    # --- Filters ---
    status = request.GET.get('status', '')
    search = request.GET.get('q', '').strip()

    if status:
        orders = orders.filter(payment_status=status)

    if search:
        orders = orders.filter(
            Q(full_name__icontains=search)
            | Q(phone__icontains=search)
            | Q(id__icontains=search)
            | Q(phonepe_order_id__icontains=search)
        )

    # --- Summary stats (always over all orders, ignoring current filters) ---
    all_orders = Order.objects.all()
    stats = {
        'total':     all_orders.count(),
        'paid':      all_orders.filter(payment_status='Paid').count(),
        'pending':   all_orders.filter(payment_status='Pending').count(),
        'failed':    all_orders.filter(payment_status__in=['Failed', 'Cancelled']).count(),
        'revenue':   all_orders.filter(payment_status='Paid').aggregate(s=Sum('total_amount'))['s'] or 0,
    }

    # --- Pagination ---
    paginator = Paginator(orders, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'adminpanel/order_list.html', {
        'page_obj': page_obj,
        'orders': page_obj,
        'status': status,
        'search': search,
        'stats': stats,
        'status_choices': Order.PAYMENT_STATUS_CHOICES,
    })

@admin_required
def order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    return render(request, 'adminpanel/order_detail.html', {
        'order': order
    })

@admin_required
def print_labels(request):
    # Only show Paid + not yet printed
    orders = Order.objects.filter(
        payment_status='Paid',
        is_printed=False
    ).order_by('-id')

    if request.method == 'POST':
        # Mark all as printed
        Order.objects.filter(
            payment_status='Paid',
            is_printed=False
        ).update(is_printed=True)
        return redirect('adminpanel:print_labels')

    return render(request, 'adminpanel/print_labels.html', {
        'orders': orders
    })


@admin_required
def export_orders_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="hasafarm_orders.csv"'

    writer = csv.writer(response)

    # Header row
    writer.writerow([
        'Order ID', 'Full Name', 'Email', 'Phone', 'Address',
        'Items Ordered', 'Total Quantity', 'Postal Charge',
        'Total Amount', 'Payment Status', 'Payment ID',
        'PhonePe Order ID', 'Order Date'
    ])

    orders = Order.objects.all().order_by('-created_at')

    # Reuse your existing status filter
    status = request.GET.get('status')
    if status:
        orders = orders.filter(payment_status=status)

    for order in orders:
        # Format cart_items JSON into readable text
        # e.g. "Tomato Seeds x2, Chili Seeds x1"
        items_text = ', '.join(
            f"{item.get('name', 'Item')} x{item.get('quantity', 1)}"
            for item in order.cart_items
        )

        writer.writerow([
            order.id,
            order.full_name,
            order.email,
            order.phone,
            order.address.replace('\n', ' '),  # flatten multiline address
            items_text,
            order.total_quantity,
            order.postal_charge,
            order.total_amount,
            order.payment_status,
            order.payment_id or '',
            order.phonepe_order_id or '',
            order.created_at.strftime('%d-%m-%Y %H:%M'),
        ])

    return response