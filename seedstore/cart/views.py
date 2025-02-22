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
        cart = request.session.get("cart", {})

        # Get quantity from request
        data = json.loads(request.body)
        quantity = int(data.get("quantity", 1))  # Default to 1 if no quantity provided

        # Check if the item is already in the cart
        if str(seed_id) in cart:
            cart[str(seed_id)]["quantity"] += quantity  # Increase quantity
        else:
            cart[str(seed_id)] = {
                "name": seed.name,
                "price": float(seed.price),  # Convert Decimal to float
                "quantity": quantity
            }

        # Save back to session
        request.session["cart"] = cart
        request.session.modified = True

        # Get unique count of items
        unique_item_count = len(cart)  # Number of unique items

        return JsonResponse({
            "message": "Item added successfully",
            "cart_count": unique_item_count,  # Unique items count
            "cart": cart
        })

    except Seed.DoesNotExist:
        return JsonResponse({"error": "Seed not found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

def view_cart(request):
    cart = request.session.get('cart', {})  # Retrieve cart from session
    cart_items = []

    for seed_id, item in cart.items():
        if not seed_id.isdigit():  # Skip invalid IDs
            continue

        try:
            seed = Seed.objects.get(id=int(seed_id))
            cart_items.append({
                'seed': seed,
                'quantity': item['quantity'],
                'total_price': seed.price * item['quantity'],
            })
        except Seed.DoesNotExist:
            continue  # Ignore missing seeds
    print("Current Cart Session:", cart)
    # print("✅ Cart ID being used:", seed_id)

    total_amount = sum(item['total_price'] for item in cart_items)

    return render(request, 'cart/cart.html', {'cart_items': cart_items, 'total_amount': total_amount})


def remove_from_cart(request, cart_id):
    if request.method == "POST":
        cart = request.session.get('cart', {})

        if str(cart_id) in cart:
            del cart[str(cart_id)]
            request.session['cart'] = cart
            request.session.modified = True

        total_amount = sum(item['price'] * item['quantity'] for item in cart.values())
        cart_count = sum(item['quantity'] for item in cart.values())

        print(f"Cart after removal: {cart}")  # Debugging
        print(f"Updated cart count: {cart_count}")  # Debugging

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
        try:
            print("Raw Request Body:", request.body)  # Debugging Line

            data = json.loads(request.body)  # This is where it fails

            print("Parsed JSON Data:", data)  # Debugging Line

            full_name = data.get("full_name")
            email = data.get("email")
            phone = data.get("phone")
            address = data.get("address")
            cart_items = data.get("cart_items")
            total_amount = data.get("total_amount")
            payment_status = data.get("payment_status", "Pending")

            if not all([full_name, email, phone, address, cart_items, total_amount]):
                return JsonResponse({"error": "Missing required fields"}, status=400)

            order = Order.objects.create(
                full_name=full_name,
                email=email,
                phone=phone,
                address=address,
                cart_items=cart_items,
                total_amount=total_amount,
                payment_status=payment_status,
            )

            return JsonResponse({"message": "Order placed successfully!", "order_id": order.id})

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON data"}, status=400)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Invalid request method"}, status=400)


def get_cart(request):
    cart = request.session.get("cart", {})
    return JsonResponse(cart)