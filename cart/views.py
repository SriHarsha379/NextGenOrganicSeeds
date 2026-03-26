from datetime import datetime, timedelta

from django.http import Http404
from django.db import transaction
from products.utils.phonepe_client import client
from decouple import config
from django.conf import settings
from django.views.decorators.http import require_POST
import hashlib
from decimal import Decimal
from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
import json, hashlib, base64, traceback

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
# from utils.phonepe_client import PhonePeClient

# client = PhonePeClient()

# Example usage:
# response = client.check_payment_status("HF444")



def add_to_cart(request, seed_id):
    try:
        seed = Seed.objects.get(id=seed_id)

        # Get or create session cart
        cart = request.session.get("cart", {})

        # Parse request body
        data = json.loads(request.body)

        # ✅ Sanitize and validate quantity
        quantity_raw = data.get("quantity", 1)

        try:
            requested_quantity = int(quantity_raw)
        except (TypeError, ValueError):
            return JsonResponse({"error": "Invalid quantity format."}, status=400)

        if requested_quantity < 1:
            return JsonResponse({"error": "Quantity must be at least 1."}, status=400)
        if requested_quantity > 999:  # Arbitrary max limit to prevent abuse
            return JsonResponse({"error": "Quantity too large."}, status=400)

        # Get current quantity in cart
        current_quantity = cart.get(str(seed_id), {}).get("quantity", 0)

        # Total quantity after addition
        new_quantity = current_quantity + requested_quantity

        if new_quantity > seed.stock:
            return JsonResponse({
                "error": f"Only {seed.stock} items available in stock! You already have {current_quantity} in your cart."
            }, status=400)

        # Update cart
        cart[str(seed_id)] = {
            "name": seed.name,
            "price": float(seed.price),
            "quantity": new_quantity
        }

        request.session["cart"] = cart
        request.session.modified = True

        return JsonResponse({
            "message": "Item added successfully",
            "cart_count": len(cart),
            "cart": cart
        })

    except Seed.DoesNotExist:
        return JsonResponse({"error": "Seed not found"}, status=404)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

logger = logging.getLogger(__name__)


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

    # ✅ Shipping logic (₹80 shipping if total below 499)
    postage_charge = 80 if total_amount < 499 else 0
    grand_total = total_amount + postage_charge

    context = {
        "cart_items": cart_items,
        "total_quantity": total_quantity,
        "total_amount": total_amount,         # leave as number
        "postage_charge": postage_charge,     # leave as number
        "grand_total": grand_total,           # leave as number
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

logger = logging.getLogger(__name__)

@csrf_exempt
def process_order(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
        logger.info("📩 Received Order Data: %s", data)

        # ✅ Step 1: Required fields validation
        required_fields = ["full_name", "email", "phone", "cart_items", "total_quantity", "total_amount"]
        missing = [f for f in required_fields if not data.get(f)]
        if missing:
            return JsonResponse({"error": f"Missing fields: {', '.join(missing)}"}, status=400)

        if not isinstance(data["cart_items"], list) or not data["cart_items"]:
            return JsonResponse({"error": "Invalid cart items"}, status=400)

        # ✅ Step 2: Address sanitization
        address = ", ".join(filter(None, [
            data.get("address_line1", ""),
            data.get("address_line2", ""),
            data.get("city", ""),
            data.get("state", ""),
            data.get("postal_code", ""),
            data.get("country", "")
        ])).strip()

        postal_charge = Decimal("80.00")
        try:
            base_amount = Decimal(str(data["total_amount"]))
            if base_amount <= 0:
                raise ValueError("Invalid total_amount")
        except:
            return JsonResponse({"error": "Invalid amount format"}, status=400)

        final_amount = base_amount + postal_charge

        with transaction.atomic():
            # ✅ Step 3: Order creation
            order = Order.objects.create(
                user=request.user if request.user.is_authenticated else None,
                full_name=data["full_name"].strip(),
                email=data["email"].strip(),
                phone=data["phone"].strip(),
                address=address,
                cart_items=data["cart_items"],
                total_quantity=int(data["total_quantity"]),
                total_amount=final_amount,
                postal_charge=postal_charge,
                payment_status="Pending"
            )

            # ✅ Step 4: Assign unique PhonePe order ID
            order.phonepe_order_id = f"HF{order.id}"
            order.save(update_fields=["phonepe_order_id"])

            # ✅ Store session key into the order
            if not request.session.session_key:
                request.session.save()
            order.session_key = request.session.session_key
            order.save(update_fields=["session_key"])

            # ✅ Step 5: Reserve stock
            for item in data["cart_items"]:
                seed = get_object_or_404(Seed.objects.select_for_update(), id=item["id"])
                qty = int(item.get("quantity", 1))
                if qty <= 0 or qty > seed.stock:
                    raise ValueError(f"Invalid quantity for seed: {seed.name}")
                seed.stock -= qty
                seed.save()

            # ✅ Step 6: Create payment link via PhonePe
            redirect_url = f"https://hasafarm.com/order/success/{order.phonepe_order_id}/"

            pay_request = StandardCheckoutPayRequest.build_request(
                merchant_order_id=order.phonepe_order_id,
                amount=int(final_amount * 100),  # in paisa
                redirect_url=redirect_url,
            )
            pay_response = client.pay(pay_request)

            # ✅ Step 7: Save payment link
            order.payment_link = pay_response.redirect_url
            order.save(update_fields=["payment_link"])

            # ✅ Step 8: Store guest order access in session
            request.session["last_order_id"] = order.id
            request.session["guest_order_id"] = str(order.id)
            request.session["last_order_time"] = datetime.utcnow().isoformat()
            request.session.modified = True

            # ✅ Step 9: Clear cart
            request.session["cart"] = {}
            request.session.modified = True

            # ✅ Step 10: Return JSON response
            return JsonResponse({
                "message": "Order created!",
                "order_id": order.id,
                "payment_link": pay_response.redirect_url,
                "postal_charge": float(postal_charge),
                "total_amount": float(final_amount)
            }, status=201)

    except ValueError as ve:
        logger.warning("❌ Validation error: %s", ve)
        return JsonResponse({"error": str(ve)}, status=400)
    except Seed.DoesNotExist:
        return JsonResponse({"error": "One or more items not found"}, status=404)
    except Exception as e:
        logger.exception("❌ Order processing error:")
        return JsonResponse({"error": "Internal Server Error"}, status=500)



def get_cart(request):
    cart = request.session.get("cart", {})
    return JsonResponse(cart)



@csrf_exempt
def clear_cart(request):
    if request.method == "POST":
        request.session["cart"] = {}
        return JsonResponse({"status": "cleared"})
    return JsonResponse({"error": "Invalid request"}, status=400)

def order_success(request, phonepe_order_id):
    try:
        order = Order.objects.get(phonepe_order_id__iexact=phonepe_order_id)
    except Order.DoesNotExist:
        raise Http404("Order not found")

    session_guest_id = str(request.session.get("guest_order_id"))
    if session_guest_id != str(order.id):
        return HttpResponseForbidden("Unauthorized access to this guest order.")

    if order.payment_status != "Paid":
        status_info = get_phonepe_payment_status(phonepe_order_id)
        if status_info["success"]:
            order.payment_status = "Paid"
            order.payment_id = status_info["payment_id"]
            order.save(update_fields=["payment_status", "payment_id"])

            # Send confirmation email to customer
            if order.email:
                items_text = "\n".join(
                    f"  • {item.get('name', 'Item')} x{item.get('quantity', 1)} — ₹{float(item.get('price', 0)) * int(item.get('quantity', 1)):.2f}"
                    for item in order.cart_items
                )
                subject = f"✅ Order Confirmed! Hasa Organic Seeds Order #{order.id}"
                message = (
                    f"Dear {order.full_name},\n\n"
                    f"Thank you for shopping with Hasa Organic Seeds! 🌱\n"
                    f"Your payment was successful and your order is confirmed.\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"ORDER SUMMARY — #{order.id}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"{items_text}\n\n"
                    f"Postal Charge : ₹{order.postal_charge}\n"
                    f"Total Amount  : ₹{order.total_amount}\n"
                    f"Payment ID    : {order.payment_id or 'N/A'}\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"SHIPPING TO\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"{order.full_name}\n"
                    f"{order.address}\n"
                    f"📞 {order.phone}\n\n"
                    f"We will notify you once your order is shipped.\n\n"
                    f"Regards,\n"
                    f"Hasa Organic Seeds\n"
                    f"📞 7483847243 | hasafarm.com"
                )
                try:
                    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [order.email])
                    logger.info("📧 Confirmation email sent to %s for order #%s", order.email, order.id)
                except Exception as e:
                    logger.error("📧 Failed to send confirmation email for order #%s: %s", order.id, e)

            # Notify admin
            try:
                admin_email = getattr(settings, 'ADMIN_NOTIFICATION_EMAIL', settings.DEFAULT_FROM_EMAIL)
                admin_message = (
                    f"Order #{order.id} — Paid\n\n"
                    f"Customer : {order.full_name}\n"
                    f"Email    : {order.email}\n"
                    f"Phone    : {order.phone}\n"
                    f"Amount   : ₹{order.total_amount}\n"
                    f"PhonePe  : {order.phonepe_order_id}\n\n"
                    f"Address:\n{order.address}"
                )
                send_mail(
                    f"[Hasafarm] Order #{order.id} — Paid",
                    admin_message,
                    settings.DEFAULT_FROM_EMAIL,
                    [admin_email],
                    fail_silently=True,
                )
                logger.info("📧 Admin notification sent for order #%s", order.id)
            except Exception as e:
                logger.error("📧 Failed to send admin email for order #%s: %s", order.id, e)

    return render(request, "cart/order_success.html", {
        "order": order,
        "pending": order.payment_status != "Paid",
    })

def get_phonepe_payment_status(order_id):
    try:
        status_response = client.get_order_status(order_id)
        state = getattr(status_response, 'state', None)
        success = (state == "COMPLETED")

        payment_id = None
        payment_details = getattr(status_response, 'payment_details', None) or []
        for pd in payment_details:
            txn_id = getattr(pd, 'transaction_id', None)
            if txn_id:
                payment_id = txn_id
                break

        return {
            "success": success,
            "payment_id": payment_id,
            "raw": status_response,
        }

    except Exception as e:
        logger.error("PhonePe status check error for order %s: %s", order_id, e)
        return {"success": False, "error": str(e), "raw": {}}

logger = logging.getLogger(__name__)

@csrf_exempt
@require_POST
def phonepe_webhook(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=405)
    # Log what we received (no secret values) so we can see what PhonePe sends
    header_keys = list(request.headers.keys())
    logger.info("🔑 Header Keys: %s", header_keys)

    auth_header = (request.headers.get("Authorization") or "").strip()

    if not auth_header:
        logger.warning("🔑 Authorization header missing")
        return JsonResponse({"error": "Unauthorized"}, status=401)

    if not auth_header.startswith("SHA256 "):
        logger.warning("🔑 Invalid auth scheme: %s", auth_header[:20])
        return JsonResponse({"error": "Unauthorized"}, status=401)

    received_hash = auth_header.replace("SHA256 ", "").strip()

    raw = settings.PHONEPE_WEBHOOK_USER + settings.PHONEPE_WEBHOOK_PASSWORD
    expected_hash = hashlib.sha256(raw.encode()).hexdigest()

    if received_hash != expected_hash:
        logger.warning("🔑 Authorization hash mismatch")
        return JsonResponse({"error": "Unauthorized"}, status=401)

    logger.info("🔐 PhonePe webhook authenticated successfully")    

    try:
        payload = json.loads(request.body.decode("utf-8"))
        logger.info("📥 Webhook received:\n%s", json.dumps(payload, indent=2))

        event_type = payload.get("event", "").lower().strip()

        data = payload.get("payload") or payload.get("data") or {}

        # ✅ Accept only valid events
        if event_type not in ["checkout.order.completed", "checkout.order.failed", "checkout.order.cancelled"]:
            logger.info("🔁 Ignored event: %s", event_type)
            return JsonResponse({"message": "Ignored event"}, status=200)

        # Docs: originalMerchantOrderId = "Order ID generated by you"; also support merchantOrderId / merchantTransactionId
        merchant_order_id = (
            data.get("originalMerchantOrderId")
            or data.get("merchantOrderId")
            or data.get("merchantTransactionId")
        )
     
        payment_id = None
        for p in (data.get("paymentDetails") or []):
            if p.get("transactionId"):
                payment_id = p["transactionId"]
                break
        
        if event_type == "checkout.order.completed":
            new_status = "Paid"
        elif event_type == "checkout.order.failed":
            new_status = "Failed"
        elif event_type == "checkout.order.cancelled":
            new_status = "Cancelled"
        else:
            return JsonResponse({"message": "Ignored"}, status=200)


        if not merchant_order_id:
            logger.error("❗ Missing merchant order id in webhook payload. Keys: %s", list(data.keys()))
            return JsonResponse({"error": "Missing merchantOrderId"}, status=400)

        try:
            order = Order.objects.get(phonepe_order_id__iexact=merchant_order_id)
        except Order.DoesNotExist:
            logger.warning("❌ Order not found for merchantOrderId: %s", merchant_order_id)
            return JsonResponse({"error": "Order not found"}, status=404)

        status_changed = (order.payment_status != new_status)

        logger.info("🔍 Order #%s current status: '%s', new status: '%s', changed: %s", 
                   order.id, order.payment_status, new_status, status_changed)

        if status_changed:
            try:
                order.payment_status = new_status
                if payment_id:
                    order.payment_id = payment_id
                order.save(update_fields=["payment_status", "payment_id"])
                logger.info("✅ Order #%s successfully updated to %s", order.id, new_status)
                order.refresh_from_db()
                logger.info("🔍 Verified: Order #%s payment_status is now '%s'", order.id, order.payment_status)
            except Exception as e:
                logger.error("❌ Failed to update order #%s: %s", order.id, str(e))
                return JsonResponse({"error": "Failed to update order status"}, status=500)

            is_paid = (new_status == "Paid")
            is_cancelled = (new_status == "Cancelled")

            # ── Email to Customer ──
            if order.email:
                # Format cart items nicely
                items_text = "\n".join(
                    f"  • {item.get('name', 'Item')} x{item.get('quantity', 1)} — ₹{float(item.get('price', 0)) * int(item.get('quantity', 1)):.2f}"
                    for item in order.cart_items
                )

                if is_paid:
                    subject = f"✅ Order Confirmed! Hasa Organic Seeds Order #{order.id}"
                    message = (
                        f"Dear {order.full_name},\n\n"
                        f"Thank you for shopping with Hasa Organic Seeds! 🌱\n"
                        f"Your payment was successful and your order is confirmed.\n\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"ORDER SUMMARY — #{order.id}\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"{items_text}\n\n"
                        f"Postal Charge : ₹{order.postal_charge}\n"
                        f"Total Amount  : ₹{order.total_amount}\n"
                        f"Payment ID    : {order.payment_id or 'N/A'}\n\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"SHIPPING TO\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"{order.full_name}\n"
                        f"{order.address}\n"
                        f"📞 {order.phone}\n\n"
                        f"We will notify you once your order is shipped.\n\n"
                        f"Regards,\n"
                        f"Hasa Organic Seeds\n"
                        f"📞 7483847243 | hasafarm.com"
                    )
                elif is_cancelled:
                    subject = f"🚫 Payment Cancelled — Hasa Organic Seeds Order #{order.id}"
                    message = (
                        f"Dear {order.full_name},\n\n"
                        f"Your payment for Order #{order.id} was cancelled.\n\n"
                        f"Total Amount : ₹{order.total_amount}\n\n"
                        f"If this was a mistake, you can place a new order at:\n"
                        f"https://hasafarm.com/cart/\n\n"
                        f"No amount has been deducted. If you see any charge, "
                        f"it will be refunded within 5-7 business days.\n\n"
                        f"Need help? Reply to this email or call 7483847243.\n\n"
                        f"Regards,\n"
                        f"Hasa Organic Seeds"
                    )
                else:
                    subject = f"❌ Payment Failed — Hasa Organic Seeds Order #{order.id}"
                    message = (
                        f"Dear {order.full_name},\n\n"
                        f"Unfortunately your payment for Order #{order.id} could not be completed.\n\n"
                        f"Total Amount : ₹{order.total_amount}\n\n"
                        f"Please try again at:\n"
                        f"https://hasafarm.com/cart/\n\n"
                        f"If you were charged, the amount will be refunded within 5-7 business days.\n\n"
                        f"Need help? Reply to this email or call 7483847243.\n\n"
                        f"Regards,\n"
                        f"Hasa Organic Seeds"
                    )

                try:
                    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [order.email])
                    logger.info("📧 Customer email sent to %s", order.email)
                except Exception as e:
                    logger.error("📧 Failed to send customer email: %s", e)

            # ── Email to Admin ──
            try:
                admin_email = getattr(settings, 'ADMIN_NOTIFICATION_EMAIL', settings.DEFAULT_FROM_EMAIL)
                admin_message = (
                    f"Order #{order.id} — {order.payment_status}\n\n"
                    f"Customer : {order.full_name}\n"
                    f"Email    : {order.email}\n"
                    f"Phone    : {order.phone}\n"
                    f"Amount   : ₹{order.total_amount}\n"
                    f"PhonePe  : {order.phonepe_order_id}\n\n"
                    f"Address:\n{order.address}"
                )
                send_mail(
                    f"[Hasafarm] Order #{order.id} — {order.payment_status}",
                    admin_message,
                    settings.DEFAULT_FROM_EMAIL,
                    [admin_email],
                    fail_silently=True,
                )
                logger.info("📧 Admin email sent")
            except Exception as e:
                logger.error("📧 Failed to send admin email: %s", e)
        else:
            logger.info("ℹ️ Order #%s already marked as %s — no change", order.id, order.payment_status)

        return JsonResponse({"message": "Webhook handled"}, status=200)

    except json.JSONDecodeError:
        logger.error("❌ Invalid JSON payload in webhook")
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except Exception as e:
        logger.exception("💥 Unexpected error during webhook processing")
        return JsonResponse({"error": "Internal server error"}, status=500)

def retry_payment(request, phonepe_order_id):
    order = get_object_or_404(Order, phonepe_order_id__iexact=phonepe_order_id)

    # 🔐 Guest session validation
    session_guest_id = str(request.session.get("guest_order_id"))
    if session_guest_id != str(order.id):
        return HttpResponseForbidden("Unauthorized access to this guest order.")

    # ✅ Retry logic
    if order.payment_status != "Paid":
        return redirect(order.payment_link or "home")

    # Already paid — show success
    return redirect("order_success", phonepe_order_id=order.phonepe_order_id)

@login_required
def my_orders(request):
    orders = Order.objects.filter(user=request.user).order_by("-created_at")
    return render(request, "cart/my_orders.html", {"orders": orders})


