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
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
        print("📩 Received Order Data:", data)

        # Validate required fields
        required_fields = ["full_name", "email", "phone", "cart_items", "total_quantity", "total_amount"]
        missing = [f for f in required_fields if not data.get(f)]
        if missing:
            return JsonResponse({"error": f"Missing fields: {', '.join(missing)}"}, status=400)

        # Build full address
        address = ", ".join([
            data.get("address_line1", ""), data.get("address_line2", ""),
            data.get("city", ""), data.get("state", ""),
            data.get("postal_code", ""), data.get("country", "")
        ])

        # Postal charge & final amount
        postal_charge = 80
        base_amount = float(data["total_amount"])
        final_amount = base_amount + postal_charge

        with transaction.atomic():
            # Step 1: Create order to generate ID
            order = Order(
                user=request.user if request.user.is_authenticated else None,
                full_name=data["full_name"],
                email=data["email"],
                phone=data["phone"],
                address=address,
                cart_items=data["cart_items"],
                total_quantity=data["total_quantity"],
                total_amount=final_amount,
                postal_charge=postal_charge,
                payment_status="Pending"
            )
            order.save()  # now order.id is available

            # Step 2: Set phonepe_order_id using order.id
            phonepe_order_id = f"HF{order.id}"
            redirect_url = f"https://hasafarm.com/order-success/?order_id={phonepe_order_id}"

            # Step 3: Reserve stock
            for item in data["cart_items"]:
                seed = Seed.objects.select_for_update().get(id=item["id"])
                qty = int(item["quantity"])
                if seed.stock < qty:
                    return JsonResponse({"error": f"Not enough stock for {seed.name}"}, status=400)
                seed.stock -= qty
                seed.save()

            # Step 4: Generate payment link via PhonePe
            pay_request = StandardCheckoutPayRequest.build_request(
                merchant_order_id=phonepe_order_id,
                amount=int(final_amount * 100),  # Convert to paise
                redirect_url=redirect_url
            )

            pay_response = client.pay(pay_request)

            # Step 5: Save order updates
            order.phonepe_order_id = phonepe_order_id
            order.payment_link = pay_response.redirect_url
            order.save(update_fields=["phonepe_order_id", "payment_link"])

            # Step 6: Clear cart from session
            request.session["cart"] = {}
            request.session.modified = True

            # Step 7: Return response
            return JsonResponse({
                "message": "Order created!",
                "order_id": order.id,
                "payment_link": pay_response.redirect_url,
                "postal_charge": postal_charge,
                "total_amount": final_amount
            }, status=201)

    except Exception as e:
        print("❌ Order error:", e)
        return JsonResponse({"error": "Internal Server Error"}, status=500)



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
    order = get_object_or_404(Order, phonepe_order_id=order_id)

    # ensure JSON cart_items
    if isinstance(order.cart_items, str):
        try:
            order.cart_items = json.loads(order.cart_items)
        except:
            order.cart_items = []

    # ✅ Check real-time status if payment is still Pending
    if order.payment_status.lower() not in ["paid", "failed"]:
        result = get_phonepe_payment_status(order.phonepe_order_id)
        if result and result.get("success"):
            state = result.get("data", {}).get("state")
            if state in ["COMPLETED", "ACTIVE"]:
                order.payment_status = "Paid"
            elif state == "FAILED":
                order.payment_status = "Failed"
            order.save()

    # Show proper UI
    if order.payment_status.lower() == "paid":
        message_title = "Payment Successful!"
        message_body  = f"Your order #{order.phonepe_order_id} is confirmed."
        btn_text      = "Continue Shopping"
        btn_link      = "/seeds/"
    elif order.payment_status.lower() == "failed":
        message_title = "Payment Failed"
        message_body  = "Your payment failed. Please try again."
        btn_text      = "Retry Payment"
        btn_link      = f"/checkout/?order_id={order.phonepe_order_id}"
    else:
        message_title = "Payment Pending"
        message_body  = "Your payment is pending. We'll notify you shortly."
        btn_text      = "Go Home"
        btn_link      = "/"

    return render(request, "cart/order_success.html", {
        "order": order,
        "message_title": message_title,
        "message_body": message_body,
        "btn_text": btn_text,
        "btn_link": btn_link
    })


def get_phonepe_payment_status(order_id):
    url = "https://api.phonepe.com/apis/hermes/pg/v1/status/{}".format(order_id)

    # Build the payload
    payload = {
        "merchantId": settings.PHONEPE_CLIENT_ID,
        "merchantTransactionId": order_id
    }

    base64_payload = base64.b64encode(json.dumps(payload).encode()).decode()

    salt = settings.PHONEPE_CLIENT_SECRET
    string_to_hash = base64_payload + "/pg/v1/status/" + order_id + salt
    x_verify = hashlib.sha256(string_to_hash.encode()).hexdigest() + "###" + settings.PHONEPE_CLIENT_VERSION

    headers = {
        "Content-Type": "application/json",
        "X-VERIFY": x_verify,
        "X-MERCHANT-ID": settings.PHONEPE_CLIENT_ID
    }

    try:
        response = requests.get(url, headers=headers)
        return response.json()
    except Exception as e:
        print("PhonePe API error:", e)
        return None


@csrf_exempt
def phonepe_webhook(request):
    print("📬 PhonePe Webhook HIT")

    # 1) Validate SHA256(username:password)
    received_auth = request.headers.get("Authorization")
    expected_auth = hashlib.sha256(
        f"{settings.PHONEPE_WEBHOOK_USERNAME}:{settings.PHONEPE_WEBHOOK_PASSWORD}".encode()
    ).hexdigest()
    if received_auth != expected_auth:
        print("❌ Invalid Authorization Header")
        return HttpResponseForbidden("Unauthorized")

    # 2) Parse the JSON body
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        print("❌ Invalid JSON Format")
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    event = payload.get("event")
    data = payload.get("payload", {})
    merchant_order_id = data.get("merchantOrderId")
    state = data.get("state")
    print(f"🔍 Event={event}  ID={merchant_order_id}  State={state}")

    if not merchant_order_id or not state:
        return JsonResponse({"error": "Missing merchantOrderId or state"}, status=400)

    # 3) Lookup and update the Order
    order = Order.objects.filter(phonepe_order_id=merchant_order_id).first()
    if not order:
        print("❌ Order not found")
        return JsonResponse({"error": "Order not found"}, status=404)

    prev = order.payment_status
    if state in ("COMPLETED", "ACTIVE"):
        order.payment_status = "Paid"
    elif state == "FAILED":
        order.payment_status = "Failed"
    else:
        order.payment_status = state
    order.save()
    print(f"✅ Order {order.phonepe_order_id}: {prev} → {order.payment_status}")

    # 4) Send emails on success
    if order.payment_status == "Paid":
        if isinstance(order.cart_items, str):
            try:
                order.cart_items = json.loads(order.cart_items)
            except:
                order.cart_items = []

        # customer
        send_mail(
            f"✅ Order Confirmed: {order.phonepe_order_id}",
            f"Hi {order.full_name},\nYour payment succeeded!\nOrder ID: {order.phonepe_order_id}\nTotal: ₹{order.total_amount}\n\nThanks for shopping!",
            settings.DEFAULT_FROM_EMAIL,
            [order.email],
            fail_silently=True
        )

        # admin
        items = "\n".join(f"- {i['name']} x{i['quantity']} = ₹{i['total_price']}" for i in order.cart_items)
        send_mail(
            f"🛒 New Paid Order: {order.phonepe_order_id}",
            f"Customer: {order.full_name}\nEmail: {order.email}\nPhone: {order.phone}\nAddress: {order.address}\n\nItems:\n{items}\n\nTotal: ₹{order.total_amount}",
            settings.DEFAULT_FROM_EMAIL,
            [settings.ADMIN_NOTIFICATION_EMAIL],
            fail_silently=False
        )

    return JsonResponse({"message": "Webhook processed successfully"})