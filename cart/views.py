from django.db import transaction
from django.conf import settings
import hashlib
import hmac
import requests
from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from .models import Cart
from products.models import Seed
from django.http import JsonResponse, HttpResponse
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


CASHFREE_APP_ID = '9795081b7f0f43691da68d756c805979'
CASHFREE_SECRET_KEY = 'cfsk_ma_prod_91757a8c50fe123563f89b3fef14c405_b16caf02'
CASHFREE_ORDER_API_URL = "https://api.cashfree.com/pg/orders"  # or live URL when live

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

            with transaction.atomic():
                order = Order.objects.create(
                    user=request.user,
                    full_name=data["full_name"],
                    email=data["email"],
                    phone=data["phone"],
                    address=address,
                    cart_items=data["cart_items"],
                    total_quantity=data["total_quantity"],
                    total_amount=data["total_amount"],
                    payment_status="Pending",
                )

                # Stock check and update
                for item in data["cart_items"]:
                    seed_id = item["id"]
                    quantity_ordered = int(item["quantity"])
                    try:
                        seed = Seed.objects.select_for_update().get(id=seed_id)
                        if seed.stock >= quantity_ordered:
                            seed.stock -= quantity_ordered
                            seed.save()
                        else:
                            return JsonResponse({"error": f"Not enough stock for {seed.name}"}, status=400)
                    except Seed.DoesNotExist:
                        return JsonResponse({"error": f"Seed with ID {seed_id} not found"}, status=404)

                # Create Cashfree Order
                cashfree_order_id = f"HASA-{order.id}"
                order_payload = {
                    "order_id": cashfree_order_id,
                    "order_amount": str(order.total_amount),
                    "order_currency": "INR",
                    "customer_details": {
                        "customer_id": str(request.user.id),
                        "customer_email": order.email,
                        "customer_phone": order.phone
                    },
                    "order_meta": {
                        "return_url": f"https://hasafarm.com/payment/confirmation?order_id={order.id}",
                        "notify_url": "https://hasafarm.com/payment/webhook/"
                    }
                }

                headers = {
                    "Content-Type": "application/json",
                    "X-Client-Id": CASHFREE_APP_ID,
                    "X-Client-Secret": CASHFREE_SECRET_KEY,
                    "x-api-version": "2022-01-01"
                }

                order_response = requests.post(CASHFREE_ORDER_API_URL, json=order_payload, headers=headers)
                order_resp_json = order_response.json()
                print("Order API Response:", order_resp_json)

                if order_response.status_code != 200 or order_resp_json.get("order_status") not in ["CREATED", "ACTIVE"]:
                    raise Exception("Cashfree Order creation failed")

                # === FIXED PART: No separate session API call ===
                payment_link = order_resp_json.get("payment_link")
                if not payment_link:
                    raise Exception("Payment link missing in order response")

                # Save payment info on order
                order.cf_order_id = cashfree_order_id
                order.order_token = order_resp_json.get("order_token")
                order.payment_link = payment_link
                order.save()

                # Clear cart
                request.session["cart"] = {}
                request.session.modified = True

                return JsonResponse({
                    "message": "Order placed successfully!",
                    "order_id": order.id,
                    "payment_link": payment_link
                }, status=201)

        except json.JSONDecodeError as e:
            print("JSON Decode Error:", e)
            return JsonResponse({"error": "Invalid JSON format"}, status=400)
        except Exception as e:
            print("Error placing order:", e)
            return JsonResponse({"error": "Internal server error"}, status=500)

    return JsonResponse({"error": "Invalid request method"}, status=405)



@login_required
def get_cart(request):
    cart = request.session.get("cart", {})
    return JsonResponse(cart)



def clear_cart(request):
    request.session["cart"] = {}  # ✅ Clear cart session
    request.session.modified = True
    return JsonResponse({"message": "Cart cleared"})

def order_success(request):
    order_id = request.GET.get("order_id")
    if not order_id:
        return render(request, "cart/order_success.html", {"error": "Order ID missing."})

    order = get_object_or_404(Order, id=order_id)

    context = {
        "order": order,
        "payment_status": order.payment_status,
    }
    return render(request, "cart/order_success.html", context)

@csrf_exempt
def cashfree_webhook_view(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid method"}, status=405)

    try:
        payload = request.body.decode("utf-8")
        data = json.loads(payload)
        print("Webhook Data Received:", data)

        received_signature = request.headers.get("X-Cf-Signature")
        if not received_signature:
            return JsonResponse({"error": "Missing signature"}, status=400)

        expected_signature = hmac.new(
            key=bytes(settings.CASHFREE_SECRET_KEY, 'utf-8'),
            msg=bytes(payload, 'utf-8'),
            digestmod=hashlib.sha256
        ).hexdigest()

        if received_signature != expected_signature:
            return JsonResponse({"error": "Invalid signature"}, status=403)

        cf_order_id = data.get("order", {}).get("order_id")
        order_status = data.get("order", {}).get("order_status")

        if not cf_order_id or not order_status:
            return JsonResponse({"error": "Invalid payload"}, status=400)

        try:
            order = Order.objects.get(cf_order_id=cf_order_id)
        except Order.DoesNotExist:
            return JsonResponse({"error": "Order not found"}, status=404)

        if order.payment_status == "Paid":
            return HttpResponse("Already processed", status=200)

        if order_status.upper() == "PAID":
            order.payment_status = "Paid"
            order.save()
            print(f"Payment successful for order {cf_order_id}")
            return HttpResponse("Payment successful", status=200)

        elif order_status.upper() == "FAILED":
            order.payment_status = "Failed"
            order.save()
            print(f"Payment failed for order {cf_order_id}")
            return HttpResponse("Payment failed", status=200)

        else:
            return JsonResponse({"error": "Unhandled status"}, status=400)

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except Exception as e:
        print("Webhook Error:", e)
        return JsonResponse({"error": "Internal server error"}, status=500)

def payment_confirmation(request):
    order_id = request.GET.get("order_id")

    if not order_id:
        return HttpResponse("Invalid order ID.", status=400)

    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        return render(request, "cart/payment_confirmation.html", {
            "message": "Order not found.",
            "status": "error"
        })

    # You can fetch payment status from webhook updates or fallback to default
    if order.payment_status == "Success":
        message = "Your payment was successful. Thank you for your order!"
        status = "success"
    elif order.payment_status == "Cancelled":
        message = "Payment was cancelled. You can try again."
        status = "cancelled"
    elif order.payment_status == "Failed":
        message = "Payment failed. Please try again or use a different method."
        status = "failed"
    else:
        message = "Your payment is still being processed. Please wait a moment."
        status = "pending"

    return render(request, "cart/payment_confirmation.html", {
        "order": order,
        "message": message,
        "status": status
    })