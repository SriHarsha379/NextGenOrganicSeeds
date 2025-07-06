from django.http import Http404
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

        # Required fields check
        required_fields = ["full_name", "email", "phone", "cart_items", "total_quantity", "total_amount"]
        missing = [f for f in required_fields if not data.get(f)]
        if missing:
            return JsonResponse({"error": f"Missing fields: {', '.join(missing)}"}, status=400)

        # Address formatting
        address = ", ".join([
            data.get("address_line1", ""), data.get("address_line2", ""),
            data.get("city", ""), data.get("state", ""),
            data.get("postal_code", ""), data.get("country", "")
        ])

        # Final amount calculation
        postal_charge = 80
        base_amount = float(data["total_amount"])
        final_amount = base_amount + postal_charge

        with transaction.atomic():
            # Step 1: Create order
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
            order.save()

            # Step 2: Assign phonepe_order_id & save early ✅
            phonepe_order_id = f"HF{order.id}"
            order.phonepe_order_id = phonepe_order_id
            order.save(update_fields=["phonepe_order_id"])

            # Step 3: Set redirect URL
            redirect_url = f"https://hasafarm.com/order-success/?order_id={phonepe_order_id}"

            # Step 4: Check & reserve stock
            for item in data["cart_items"]:
                seed = Seed.objects.select_for_update().get(id=item["id"])
                qty = int(item["quantity"])
                if seed.stock < qty:
                    return JsonResponse({"error": f"Not enough stock for {seed.name}"}, status=400)
                seed.stock -= qty
                seed.save()

            # Step 5: PhonePe payment link
            pay_request = StandardCheckoutPayRequest.build_request(
                merchant_order_id=phonepe_order_id,
                amount=int(final_amount * 100),
                redirect_url=redirect_url
            )
            pay_response = client.pay(pay_request)

            # Step 6: Save payment link
            order.payment_link = pay_response.redirect_url
            order.save(update_fields=["payment_link"])

            # Step 7: Clear session cart
            request.session["cart"] = {}
            request.session.modified = True

            # Step 8: Return success response
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
    order_id = order_id.strip() if order_id else None

    # ✅ Try matching by phonepe_order_id first
    order = Order.objects.filter(phonepe_order_id__iexact=order_id).first()

    # ✅ Fallback to numeric ID
    if not order and order_id and order_id.isdigit():
        order = Order.objects.filter(id=int(order_id)).first()

    if not order:
        raise Http404("Order not found")

    # Decode JSON safely
    if isinstance(order.cart_items, str):
        try:
            order.cart_items = json.loads(order.cart_items)
        except:
            order.cart_items = []

    # Real-time payment check if still pending
    if order.payment_status.lower() not in ["paid", "failed"]:
        result = get_phonepe_payment_status(order.phonepe_order_id)
        if result and result.get("success"):
            state = result.get("data", {}).get("state")
            if state in ["COMPLETED", "ACTIVE"]:
                order.payment_status = "Paid"
            elif state == "FAILED":
                order.payment_status = "Failed"
            order.save()

    # UI rendering
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
    try:
        salt_key = settings.PHONEPE_SALT_KEY
        salt_index = settings.PHONEPE_SALT_INDEX
        merchant_id = settings.PHONEPE_MERCHANT_ID

        url_path = f"/pg/v1/status/{order_id}"
        base_url = "https://api.phonepe.com"  # for production
        full_url = base_url + url_path

        string_to_hash = f"{url_path}{salt_key}"
        hashed = hashlib.sha256(string_to_hash.encode()).hexdigest()
        x_verify = f"{hashed}###{salt_index}"

        headers = {
            "X-VERIFY": x_verify,
            "X-MERCHANT-ID": merchant_id,
            "Content-Type": "application/json"
        }

        response = requests.get(full_url, headers=headers, timeout=10)
        return response.json()

    except Exception as e:
        print("❌ PhonePe status check error:", e)
        return {}


@csrf_exempt
def phonepe_webhook(request):
    logger.info("📬 PhonePe Webhook HIT")


    # ✅ Basic Auth Validation
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Basic '):
        return HttpResponseForbidden("Unauthorized")

    try:
        encoded_credentials = auth_header.split(' ')[1]
        decoded_credentials = base64.b64decode(encoded_credentials).decode('utf-8')
        username, password = decoded_credentials.split(':', 1)
    except Exception:
        return HttpResponseForbidden("Unauthorized")
    print("🚨 Incoming Authorization:", request.headers.get('Authorization'))

    if username != settings.PHONEPE_WEBHOOK_USERNAME or password != settings.PHONEPE_WEBHOOK_PASSWORD:
        return HttpResponseForbidden("Unauthorized")

    # ✅ Parse JSON
    try:
        payload = json.loads(request.body)
        logger.info(f"Payload: {payload}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    event = payload.get("event")
    data = payload.get("payload", {})
    merchant_order_id = data.get("merchantOrderId") or data.get("merchantTransactionId")
    state = data.get("state")

    # ✅ Ignore unknown event types
    if event not in ["checkout.order.completed", "checkout.order.failed"]:
        logger.warning(f"Ignoring unknown event: {event}")
        return JsonResponse({"message": "Ignored"}, status=200)

    if not merchant_order_id or not state:
        return JsonResponse({"error": "Missing merchantOrderId or state"}, status=400)

    order = Order.objects.filter(phonepe_order_id=merchant_order_id).first()
    if not order:
        return JsonResponse({"error": "Order not found"}, status=404)

    previous_status = order.payment_status

    if previous_status == "Paid":
        logger.info(f"🔁 Duplicate webhook for already Paid order {order.phonepe_order_id}")
        return JsonResponse({"message": "Already paid"}, status=200)

    if state in ("COMPLETED", "ACTIVE"):
        order.payment_status = "Paid"
    elif state == "FAILED":
        order.payment_status = "Failed"
    else:
        order.payment_status = state

    # Optional: Save PhonePe transaction ID
    txn_id = data.get("transactionId")
    if txn_id:
        order.payment_id = txn_id

    order.save()
    logger.info(f"✅ Payment status updated: {previous_status} → {order.payment_status}")

    # 📨 Send email only on first successful payment
    if order.payment_status == "Paid" and previous_status != "Paid":
        if isinstance(order.cart_items, str):
            try:
                order.cart_items = json.loads(order.cart_items)
            except:
                order.cart_items = []

        # Send customer mail
        send_mail(
            f"✅ Order Confirmed: {order.phonepe_order_id}",
            f"Hi {order.full_name},\nYour payment succeeded!\nOrder ID: {order.phonepe_order_id}\nTotal: ₹{order.total_amount}",
            settings.DEFAULT_FROM_EMAIL,
            [order.email],
            fail_silently=True,
        )

        # Send admin mail
        items = "\n".join(f"- {i['name']} x{i['quantity']} = ₹{i['total_price']}" for i in order.cart_items)
        send_mail(
            f"🛒 New Paid Order: {order.phonepe_order_id}",
            f"Customer: {order.full_name}\nEmail: {order.email}\nPhone: {order.phone}\nAddress: {order.address}\n\nItems:\n{items}\n\nTotal: ₹{order.total_amount}",
            settings.DEFAULT_FROM_EMAIL,
            [settings.ADMIN_NOTIFICATION_EMAIL],
            fail_silently=False,
        )
    print("🧪 ENV DEBUG — Username:", settings.PHONEPE_WEBHOOK_USERNAME)
    print("🧪 ENV DEBUG — Password:", settings.PHONEPE_WEBHOOK_PASSWORD)
    return JsonResponse({"message": "Webhook processed successfully"}, status=200)