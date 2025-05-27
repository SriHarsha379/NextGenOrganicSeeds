from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db import transaction

from cart.models import Cart
from .models import  Order
from django.core.mail import send_mail
from django.utils.crypto import get_random_string

@login_required
def checkout(request):
    cart_items = Cart.objects.filter(user=request.user)
    total_amount = sum(item.total_price() for item in cart_items)

    if request.method == "POST":
        full_name = request.POST["full_name"]
        email = request.POST["email"]
        phone = request.POST["phone"]
        address = request.POST["address"]

        with transaction.atomic():
            # Store all cart items inside `cart_items` JSONField
            order_data = [
                {"seed": item.seed.name, "quantity": item.quantity, "price": item.total_price()}
                for item in cart_items
            ]
            order_id = get_random_string(10).upper()  # Generate a unique order ID

            order = Order.objects.create(
                user=request.user,
                full_name=full_name,
                email=email,
                phone=phone,
                address=address,
                cart_items=order_data,  # Store cart as JSON
                total_quantity=sum(item.quantity for item in cart_items),
                total_amount=total_amount,
                payment_status="Pending",
                payment_id=order_id,  # Temporary order ID
            )

            cart_items.delete()  # Clear cart after placing the order

        # Send order confirmation email
        send_mail(
            "Order Confirmation - Next Gen Organic Seeds",
            f"Hello {full_name},\n\nYour order has been placed successfully!\n\nOrder ID: {order_id}\nTotal: ₹{total_amount}\n\nThank you for shopping with us!",
            "yourstore@example.com",
            [email],
            fail_silently=False,
        )

        return redirect("order_success", order_id=order_id)  # Redirect to success page

    return render(request, "orders/checkout.html", {"cart_items": cart_items, "total_amount": total_amount})


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
