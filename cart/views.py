from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from .models import Cart
from products.models import Seed
from django.http import JsonResponse
from django.contrib.auth.models import User
import logging
import json
from django.views.decorators.csrf import csrf_exempt
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
        requested_quantity = int(data.get("quantity", 1))  # Default to 1 if not provided

        # Get current quantity in cart (default to 0 if not in cart)
        current_quantity = cart[str(seed_id)]["quantity"] if str(seed_id) in cart else 0

        # New total quantity after adding
        new_quantity = current_quantity + requested_quantity

        # ✅ Validate against available stock
        if new_quantity > seed.stock:
            return JsonResponse({
                "error": f"Only {seed.stock} items available in stock! You already have {current_quantity} in your cart."
            }, status=400)

        # Update cart quantity
        if str(seed_id) in cart:
            cart[str(seed_id)]["quantity"] = new_quantity  # Update existing quantity
        else:
            cart[str(seed_id)] = {
                "name": seed.name,
                "price": float(seed.price),  # Convert Decimal to float
                "quantity": requested_quantity
            }

        # Save back to session
        request.session["cart"] = cart
        request.session.modified = True

        # Get unique count of items
        unique_item_count = len(cart)  # Number of unique items

        return JsonResponse({
            "message": "Item added successfully",
            "cart_count": unique_item_count,
            "cart": cart
        })

    except Seed.DoesNotExist:
        return JsonResponse({"error": "Seed not found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

logger = logging.getLogger(__name__)

@login_required
def view_cart(request):
    cart = request.session.get('cart', {})  # Retrieve cart from session
    seed_ids = [int(seed_id) for seed_id in cart.keys() if seed_id.isdigit()]

    # ✅ Fetch all seeds in a single query to reduce DB hits
    seeds = Seed.objects.filter(id__in=seed_ids)
    seed_map = {seed.id: seed for seed in seeds}  # Dict for quick lookup

    cart_items = []
    total_amount = 0

    for seed_id, item in cart.items():
        if not seed_id.isdigit():  # Skip invalid IDs
            continue

        seed_id = int(seed_id)
        seed = seed_map.get(seed_id)  # Get seed from pre-fetched dict

        if not seed:
            continue  # Skip missing seeds

        quantity = item.get('quantity', 1)
        total_price = seed.price * quantity
        cart_items.append({
            'seed': seed,
            'quantity': quantity,
            'total_price': total_price,
        })
        total_amount += total_price  # ✅ Calculate total efficiently

    # Debugging (Optional)
    logger.info(f"User {request.user} Cart: {cart}")  # Log session cart

    return render(request, 'cart/cart.html', {
        'cart_items': cart_items,
        'total_amount': total_amount
    })

@login_required
def remove_from_cart(request, cart_id):
    if request.method == "POST":
        cart = request.session.get('cart', {})

        if str(cart_id) in cart:
            cart.pop(str(cart_id))  # More efficient than `del`
            request.session['cart'] = cart
            request.session.modified = True

            # Calculate the updated total and cart count
            total_amount = sum(item['price'] * item['quantity'] for item in cart.values())
            cart_count = sum(item['quantity'] for item in cart.values())

            # Return updated cart count and total amount to the client
            return JsonResponse({
                "message": "Item removed from cart!",
                "cart_count": cart_count,
                "total_amount": total_amount
            })

        return JsonResponse({"message": "Item not found!"}, status=404)



def get_cart_summary(cart):
    cart_items = []
    total_quantity = 0
    total_amount = 0

    for seed_id, item in cart.items():
        item_total = item["quantity"] * item["price"]
        cart_items.append({
            "id": seed_id,
            "name": item["name"],
            "price": f"{item['price']:.2f}",  # Ensuring proper price format
            "quantity": item["quantity"],
            "total_price": f"{item_total:.2f}"
        })
        total_quantity += item["quantity"]
        total_amount += item_total

    return cart_items, total_quantity, total_amount

def checkout(request):
    cart = request.session.get("cart", {})
    cart_items, total_quantity, total_amount = get_cart_summary(cart)

    context = {
        "cart_items": cart_items,
        "total_quantity": total_quantity,
        "total_amount": f"{total_amount:.2f}"  # Formatting amount
    }
    return render(request, "cart/checkout.html", context)



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


@csrf_exempt
@login_required
def process_order(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body.decode("utf-8"))
            print("Received Data:", data)

            address = f"{data.get('address_line1', '')}, {data.get('address_line2', '')}, {data.get('city', '')}, {data.get('state', '')}, {data.get('postal_code', '')}, {data.get('country', '')}"

            required_fields = ["full_name", "email", "phone", "cart_items", "total_quantity", "total_amount"]
            missing_fields = [field for field in required_fields if field not in data or not data[field]]

            if missing_fields:
                return JsonResponse({"error": f"Missing required fields: {', '.join(missing_fields)}"}, status=400)

            # ✅ Create order
            order = Order.objects.create(
                user=request.user,
                full_name=data["full_name"],
                email=data["email"],
                phone=data["phone"],
                address=address,
                cart_items=data["cart_items"],
                total_quantity=data["total_quantity"],
                total_amount=data["total_amount"],
                payment_status=data.get("payment_status", "Pending"),
            )

            # ✅ Update stock
            for item in data["cart_items"]:
                seed_id = item["id"]
                quantity_ordered = int(item["quantity"])

                try:
                    seed = Seed.objects.get(id=seed_id)
                    if seed.stock >= quantity_ordered:
                        seed.stock -= quantity_ordered
                        seed.save()
                    else:
                        return JsonResponse({"error": f"Not enough stock for {seed.name}"}, status=400)
                except Seed.DoesNotExist:
                    return JsonResponse({"error": f"Seed with ID {seed_id} not found"}, status=404)

            # ✅ Clear cart
            request.session["cart"] = {}
            request.session.modified = True

            return JsonResponse({"message": "Order placed successfully!", "order_id": order.id}, status=201)

        except json.JSONDecodeError as e:
            print("JSON Decode Error:", e)
            return JsonResponse({"error": "Invalid JSON format"}, status=400)

    return JsonResponse({"error": "Invalid request method"}, status=405)




@login_required
def get_cart_count(request):
    cart = request.session.get("cart", {})
    cart_count = len(cart)
    return JsonResponse({"cart_count": cart_count})


def clear_cart(request):
    request.session["cart"] = {}  # ✅ Clear cart session
    request.session.modified = True
    return JsonResponse({"message": "Cart cleared"})

def order_success(request):
    return render(request, "cart/order_success.html")
