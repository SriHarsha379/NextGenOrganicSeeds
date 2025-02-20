from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db import transaction
from .models import Cart, Order
from .utils import generate_upi_payment_link  # Implement this function

@login_required
def checkout(request):
    cart_items = Cart.objects.filter(user=request.user)
    total_amount = sum(item.total_price() for item in cart_items)

    if request.method == "POST":
        with transaction.atomic():  # Ensure atomicity
            orders = []
            for item in cart_items:
                order = Order.objects.create(
                    user=request.user,
                    seed=item.seed,
                    quantity=item.quantity,
                    total_amount=item.total_price(),
                    status="Pending",
                )
                orders.append(order)

            cart_items.delete()  # Only delete after orders are created

        # Generate UPI payment link (implement this in utils.py)
        upi_link = generate_upi_payment_link(request.user, total_amount)

        # Redirect to UPI payment page with payment link
        return redirect(f'/upi-payment/?upi_link={upi_link}')

    return render(request, 'orders/checkout.html', {'cart_items': cart_items, 'total_amount': total_amount})


@login_required
def upi_payment(request):
    upi_link = request.GET.get("upi_link")
    if not upi_link:
        return redirect("checkout")  # Redirect back if no UPI link found
    return render(request, "orders/upi_payment.html", {"upi_link": upi_link})


@login_required
def payment_success(request):
    # Here, you should verify the payment via UPI API before updating order status
    orders = Order.objects.filter(user=request.user, status="Pending")
    orders.update(status="Completed")
    return render(request, "orders/payment_success.html")
