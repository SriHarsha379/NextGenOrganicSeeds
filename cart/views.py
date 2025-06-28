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
                redirect_url = f"https://hasafarm.com/order-success/?order_id={phonepe_order_id}"


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

    # Based on payment status
    if order.payment_status in ["Paid", "SUCCESS", "PAID"]:
        message_title = "✅ Payment Successful!"
        message_body = f"Thank you for your order #{order.id}. We've received your payment."
        btn_text = "Continue Shopping"
        btn_link = "/seeds/"
    elif order.payment_status == "Failed":
        message_title = "❌ Payment Failed"
        message_body = "Unfortunately, your payment failed. Please try again."
        btn_text = "Retry Payment"
        btn_link = f"/checkout/?order_id={order.phonepe_order_id}"
    else:
        message_title = "⏳ Payment Pending"
        message_body = "We're waiting to confirm your payment. You'll be notified shortly."
        btn_text = "Go Home"
        btn_link = "/"

    return render(request, "cart/order_success.html", {
        "order": order,
        "message_title": message_title,
        "message_body": message_body,
        "btn_text": btn_text,
        "btn_link": btn_link,
        "payment_status": order.payment_status
    })




@csrf_exempt
def phonepe_webhook(request):
    try:
        # Step 1: Auth check
        received_auth = request.headers.get("Authorization")
        expected_auth = hashlib.sha256(
            f"{config('PHONEPE_WEBHOOK_USERNAME')}:{config('PHONEPE_WEBHOOK_PASSWORD')}".encode()
        ).hexdigest()

        if received_auth != expected_auth:
            return HttpResponseForbidden("Unauthorized")

        # Step 2: Extract and validate payload
        payload = json.loads(request.body)
        print("📩 Webhook Payload:", payload)

        event_type = payload.get("event")
        data = payload.get("payload", {})
        merchant_order_id = data.get("merchantOrderId")  # Example: HF123
        payment_status = data.get("state")  # COMPLETED, FAILED, etc.

        if not merchant_order_id or not payment_status:
            return JsonResponse({"error": "Missing order info"}, status=400)

        # Step 3: Find order by phonepe_order_id
        order = Order.objects.filter(phonepe_order_id=merchant_order_id).first()
        if not order:
            return JsonResponse({"error": "Order not found"}, status=404)

        # Step 4: Update payment status
        if payment_status == "COMPLETED":
            order.payment_status = "Paid"
        elif payment_status == "FAILED":
            order.payment_status = "Failed"
        else:
            order.payment_status = payment_status  # catch unexpected states

        order.save()
        print(f"✅ Order {order.id} status updated to {order.payment_status}")

        # Step 5: Send confirmation emails
        if order.payment_status == "Paid":
            # notify admin
            send_mail(
                subject=f"✅ New Paid Order - #{order.id}",
                message=f"Order placed by {order.full_name} for ₹{order.total_amount}",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[settings.ADMIN_NOTIFICATION_EMAIL],
                fail_silently=True,
            )

            # confirmation to customer
            send_mail(
                subject=f"Your Order with Hasa Farm #{order.id} is Confirmed 🎉",
                message=f"Hi {order.full_name},\n\nThank you for your payment of ₹{order.total_amount}. Your order is confirmed!",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[order.email],
                fail_silently=True,
            )

        return JsonResponse({"message": "Webhook processed successfully"})

    except Exception as e:
        print("🚨 Webhook error:", e)
        return JsonResponse({"error": "Internal server error"}, status=500)


def check_order_status(request):
    order_id = request.GET.get("order_id")
    if not order_id:
        return JsonResponse({"status": "error", "message": "Order ID not provided"}, status=400)

    order = Order.objects.filter(phonepe_order_id=order_id).first()
    if not order:
        return JsonResponse({"status": "error", "message": "Order not found"}, status=404)

    return JsonResponse({"status": order.payment_status})
