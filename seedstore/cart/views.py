from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from .models import Cart
from products.models import Seed
from django.http import JsonResponse
from django.contrib.auth.models import User
import json
from django.db.models import Sum
from django.contrib import messages
from orders.models import Order


def add_to_cart(request, seed_id):
    try:
        seed = Seed.objects.get(id=seed_id)

        # Get or create session cart
        cart = request.session.get('cart', {})

        # Ensure price is stored as a float
        cart[seed_id] = {
            "name": seed.name,
            "price": float(seed.price),  # Convert Decimal to float
            "quantity": cart.get(seed_id, {}).get("quantity", 0) + 1
        }

        # Save back to session
        request.session["cart"] = cart
        request.session.modified = True

        return JsonResponse({"message": "Item added successfully"})

    except Seed.DoesNotExist:
        return JsonResponse({"error": "Seed not found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

def view_cart(request):
    cart = request.session.get('cart', {})  # Retrieve cart from session
    cart_items = []

    for seed_id, item in cart.items():
        try:
            seed = Seed.objects.get(id=seed_id)  # Fetch seed from DB
            cart_items.append({
                'seed': seed,  # Pass the entire seed object
                'quantity': item['quantity'],
                'total_price': seed.price * item['quantity'],
            })
        except Seed.DoesNotExist:
            continue  # Ignore if seed doesn't exist

    total_amount = sum(item['total_price'] for item in cart_items)

    return render(request, 'cart/cart.html', {'cart_items': cart_items, 'total_amount': total_amount})


def remove_from_cart(request, cart_id):  # Change seed_id to cart_id
    if request.method == "POST":
        cart = request.session.get('cart', {})

        if str(cart_id) in cart:
            del cart[str(cart_id)]
            request.session['cart'] = cart
            request.session.modified = True

        total_amount = sum(item['price'] * item['quantity'] for item in cart.values())
        cart_count = sum(item['quantity'] for item in cart.values())

        return JsonResponse({
            "message": "Item removed from cart!",
            "cart_count": cart_count,
            "total_amount": total_amount
        })



def checkout(request):
    cart = request.session.get('cart', {})  # Get cart from session
    total_amount = sum(item['price'] * item['quantity'] for item in cart.values())

    return render(request, 'cart/checkout.html', {
        'cart_items': cart.values(),
        'total_amount': total_amount
    })


def update_cart_quantity(request, item_id):
    if request.method == "POST":
        cart_item = get_object_or_404(Cart, id=item_id, user=request.user)
        new_quantity = int(request.POST.get('quantity', 1))

        if new_quantity > 0:
            cart_item.quantity = new_quantity
            cart_item.save()
            return JsonResponse({'message': 'Quantity updated successfully!'})
        else:
            cart_item.delete()  # Remove item if quantity is 0
            return JsonResponse({'message': 'Item removed from cart!'})

    return JsonResponse({'error': 'Invalid request'}, status=400)

def process_order(request):
    if request.method == "POST":
        full_name = request.POST.get("full_name")
        email = request.POST.get("email")
        phone = request.POST.get("phone")
        address = request.POST.get("address")

        cart = request.session.get('cart', {})
        total_amount = sum(item['price'] * item['quantity'] for item in cart.values())

        order = Order.objects.create(
            full_name=full_name,
            email=email,
            phone=phone,
            address=address,
            total_amount=total_amount,
            payment_status="Pending",  # Can be updated later
        )

        # Clear session cart after order is placed
        request.session['cart'] = {}
        request.session.modified = True

        return redirect("payment_page")  # Redirect to payment processing
