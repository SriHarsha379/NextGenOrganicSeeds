from django.db import transaction
from products.utils.phonepe_client import client
from decouple import config
from django.conf import settings
from django.views.decorators.http import require_POST
import hashlib
import hmac
import requests
from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
import json, hmac, hashlib, base64, traceback

from phonepe.sdk.pg.payments.v2.models.request.standard_checkout_pay_request import StandardCheckoutPayRequest

from .models import Cart
from products.models import Seed
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden
from django.contrib.auth.models import User
import logging
import json
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Sum
from django.contrib import messages
from orders.models import Order
from django.core.mail import send_mail, EmailMessage


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
    seeds = Seed.objects.filter(id__in=seed_ids)
    seed_map = {seed.id: seed for seed in seeds}  # Dict for quick lookup

    cart_items = []
    total_amount = 0

    for seed_id, item in cart.items():
        if not seed_id.isdigit():
            continue
        seed_id = int(seed_id)
        seed = seed_map.get(seed_id)
        if not seed:
            continue

        quantity = item.get('quantity', 1)
        total_price = seed.price * quantity
        cart_items.append({
            'seed': seed,
            'quantity': quantity,
            'total_price': total_price,
        })
        total_amount += total_price

    # ✅ Add a fixed postage charge (you can make this dynamic if needed)
    POSTAGE_CHARGE = 80  # ₹49 shipping cost
    grand_total = total_amount + POSTAGE_CHARGE

    return render(request, 'cart/cart.html', {
        'cart_items': cart_items,
        'total_amount': total_amount,
        'postage_charge': POSTAGE_CHARGE,
        'grand_total': grand_total,
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

    # ✅ Shipping logic (free if above ₹499)
    postage_charge = 0
    grand_total = total_amount + postage_charge

    context = {
        "cart_items": cart_items,
        "total_quantity": total_quantity,
        "total_amount": f"{total_amount:.2f}",
        "postage_charge": f"{postage_charge:.2f}",
        "grand_total": f"{grand_total:.2f}",
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


# CASHFREE_APP_ID = '9795081b7f0f43691da68d756c805979'
# CASHFREE_SECRET_KEY = 'cfsk_ma_prod_91757a8c50fe123563f89b3fef14c405_b16caf02'
# CASHFREE_ORDER_API_URL = "https://api.cashfree.com/pg/orders"  # or live URL when live

@csrf_exempt
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

            postal_charge = 80
            base_total = float(data["total_amount"])
            final_amount = base_total + postal_charge

            with transaction.atomic():
                order = Order.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    full_name=data["full_name"],
                    email=data["email"],
                    phone=data["phone"],
                    address=address,
                    cart_items=data["cart_items"],
                    total_quantity=data["total_quantity"],
                    total_amount=final_amount,
                    postal_charge=postal_charge,
                    payment_status="Pending",
                )

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

                # Create PhonePe Payment
                phonepe_order_id = f"HF{order.id}"
                redirect_url = "https://hasafarm.com/order-success/"

                pay_request = StandardCheckoutPayRequest.build_request(
                    merchant_order_id=phonepe_order_id,
                    amount=int(final_amount * 100),
                    redirect_url=redirect_url
                )

                pay_response = client.pay(pay_request)

                order.phonepe_order_id = phonepe_order_id
                order.payment_link = pay_response.redirect_url
                order.save()

                # Clear cart session
                request.session["cart"] = {}
                request.session.modified = True

                return JsonResponse({
                    "message": "Order placed successfully!",
                    "order_id": order.id,
                    "payment_link": pay_response.redirect_url,
                    "postal_charge": postal_charge,
                    "total_amount": final_amount
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
    order_id = request.GET.get('order_id')
    if not order_id:
        return render(request, "cart/order_success.html", {
            "error": "Order ID missing.",
            "message_title": "Order Error",
            "message_body": "No order ID was provided.",
            "btn_text": "Go Home",
            "btn_link": "/"
        })

    order = get_object_or_404(Order, phonepe_order_id=order_id)

    # Deserialize cart_items if needed
    if isinstance(order.cart_items, str):
        try:
            order.cart_items = json.loads(order.cart_items)
        except json.JSONDecodeError:
            order.cart_items = []

    # Determine messages based on payment status
    if order.payment_status in ["Paid", "SUCCESS", "PAID"]:
        message_title = "Payment Successful!"
        message_body = f"Thank you for your order #{order.id}. We've received your payment."
        btn_text = "Continue Shopping"
        btn_link = "/seeds/"
    elif order.payment_status == "Failed":
        message_title = "Payment Failed"
        message_body = "Unfortunately, your payment failed. Please try again."
        btn_text = "Retry Payment"
        btn_link = f"/checkout/?order_id={order.phonepe_order_id}"
    else:
        message_title = "Payment Pending"
        message_body = "We're waiting to confirm your payment. You'll be notified once it's complete."
        btn_text = "Go Home"
        btn_link = "/"

    context = {
        "order": order,
        "payment_status": order.payment_status,
        "message_title": message_title,
        "message_body": message_body,
        "btn_text": btn_text,
        "btn_link": btn_link
    }
    return render(request, "cart/order_success.html", context)




@csrf_exempt
def phonepe_webhook(request):
    # Step 1: Extract Authorization header
    received_auth = request.headers.get("Authorization")

    # Step 2: Generate expected SHA256(username:password)
    username = config("PHONEPE_WEBHOOK_USERNAME")
    password = config("PHONEPE_WEBHOOK_PASSWORD")
    auth_string = f"{username}:{password}"
    expected_auth = hashlib.sha256(auth_string.encode()).hexdigest()

    # Step 3: Validate authorization
    if received_auth != expected_auth:
        return HttpResponseForbidden("Unauthorized")

    try:
        payload = json.loads(request.body)
        print("📩 PhonePe Webhook Payload:", payload)

        event_type = payload.get("event")
        data = payload.get("payload", {})
        merchant_order_id = data.get("merchantOrderId")
        payment_status = data.get("state")  # "COMPLETED", "FAILED", etc.

        if not merchant_order_id or not payment_status:
            return JsonResponse({"error": "Missing order info"}, status=400)

        # Step 4: Get Order
        order = Order.objects.filter(phonepe_order_id=merchant_order_id).first()
        if not order:
            return JsonResponse({"error": "Order not found"}, status=404)

        # Step 5: Update payment status
        order.payment_status = (
            "Paid" if payment_status == "COMPLETED"
            else "Failed" if payment_status == "FAILED"
            else payment_status
        )
        order.save()

        # Step 6: Send email if payment is successful
        if payment_status == "COMPLETED":
            subject = f"✅ New Paid Order - Order #{order.id}"
            message = f"""
📦 New Paid Order Received!

👤 Name: {order.full_name}
📧 Email: {order.email}
📞 Phone: {order.phone}
🏠 Address: {order.address}
📦 Quantity: {order.total_quantity}
💰 Total: ₹{order.total_amount}

🛒 Items:
"""
            for item in order.cart_items:
                message += f"- {item['name']} x {item['quantity']} = ₹{item['total_price']}\n"

            message += "\nPlease process and dispatch this order."

            # Send email to admin (you)
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [settings.ADMIN_NOTIFICATION_EMAIL],
                fail_silently=False,
            )

            # Confirmation email to customer
            send_mail(
                f"Your Order with Hasa Farm (#{order.id}) is Confirmed 🎉",
                f"Hi {order.full_name},\n\nThank you for your payment! Your order is now confirmed and will be processed shortly.\n\nTotal Paid: ₹{order.total_amount}\n\nRegards,\nHasa Farm",
                settings.DEFAULT_FROM_EMAIL,
                [order.email],
                fail_silently=True,
            )

        return JsonResponse({"message": "Webhook processed successfully"})

    except Exception as e:
        print("Webhook Error:", e)
        return JsonResponse({"error": "Internal Server Error"}, status=500)