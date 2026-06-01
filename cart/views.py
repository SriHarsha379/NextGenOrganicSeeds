import base64
import json
import logging
from datetime import datetime
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.mail import EmailMultiAlternatives, send_mail
from django.db import transaction
from django.http import Http404, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.views.decorators.csrf import csrf_exempt

from phonepe.sdk.pg.payments.v2.models.request.standard_checkout_pay_request import StandardCheckoutPayRequest

from .models import Cart
from orders.models import Order
from products.models import Seed
from products.utils.phonepe_client import client

logger = logging.getLogger(__name__)



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
        except (ValueError, TypeError, KeyError):
            return JsonResponse({"error": "Invalid amount format"}, status=400)

        final_amount = base_amount + postal_charge

        with transaction.atomic():
            # Step 3: Ensure session key exists before creating the order
            if not request.session.session_key:
                request.session.save()

            # Step 4: Create order
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
                payment_status="Pending",
                phonepe_order_id=None,
                session_key=request.session.session_key,
            )

            # Assign unique PhonePe order ID and save (session_key already set during create)
            order.phonepe_order_id = f"HF{order.id}"
            order.save(update_fields=["phonepe_order_id"])

            # Step 5: Reserve stock
            for item in data["cart_items"]:
                seed = get_object_or_404(Seed.objects.select_for_update(), id=item["id"])
                qty = int(item.get("quantity", 1))
                if qty <= 0 or qty > seed.stock:
                    raise ValueError(f"Invalid quantity for seed: {seed.name}")
                seed.stock -= qty
                seed.save()

            # Step 6: Create payment link via PhonePe
            redirect_url = f"https://hasafarm.com/order/success/{order.phonepe_order_id}/"

            pay_request = StandardCheckoutPayRequest.build_request(
                merchant_order_id=order.phonepe_order_id,
                amount=int(final_amount * 100),  # in paisa
                redirect_url=redirect_url,
            )
            pay_response = client.pay(pay_request)

            # Step 7: Save payment link
            order.payment_link = pay_response.redirect_url
            order.save(update_fields=["payment_link"])

            # Step 8: Store guest order access in session
            request.session["last_order_id"] = order.id
            request.session["guest_order_id"] = str(order.id)
            request.session["last_order_time"] = datetime.utcnow().isoformat()
            request.session["cart"] = {}
            request.session.modified = True

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

    # Authorization rules:
    #  • Registered-user orders (order.user is set): require the owner to be logged in,
    #    OR accept the session guest_order_id as a fallback (covers the redirect
    #    immediately after checkout before the user logs back in).
    #  • Guest orders (order.user is None): the unguessable phonepe_order_id acts as
    #    the access token — any holder of the link can view the page.
    if order.user is not None:
        session_guest_id = request.session.get("guest_order_id")
        is_owner = (
            (request.user.is_authenticated and order.user == request.user)
            or (session_guest_id is not None and str(session_guest_id) == str(order.id))
        )
        if not is_owner:
            return HttpResponseForbidden("Unauthorized access to this order.")

    if order.payment_status != "Paid":
        status_info = _check_phonepe_payment_status(phonepe_order_id)
        if status_info["success"]:
            updated = False
            try:
                with transaction.atomic():
                    order = Order.objects.select_for_update().get(id=order.id)
                    if order.payment_status != "Paid":
                        order.payment_status = "Paid"
                        if status_info.get("payment_id"):
                            order.payment_id = status_info["payment_id"]
                        order.save(update_fields=["payment_status", "payment_id"])
                        updated = True
                        logger.info("✅ Order #%s marked Paid via order_success page", order.id)
            except Exception as e:
                logger.error("❌ DB update failed in order_success for order #%s: %s", order.id, e)

            if updated:
                order.refresh_from_db()
                _send_order_status_emails(order, "Paid")

    return render(request, "cart/order_success.html", {
        "order": order,
        "pending": order.payment_status != "Paid",
    })

def _check_phonepe_payment_status(order_id):
    """Internal helper: calls PhonePe status API and returns a plain dict.

    Returns:
        dict with keys:
            success (bool)   – True when PhonePe state is COMPLETED
            state   (str)    – raw state string from PhonePe
            payment_id (str) – first transaction_id found, or None
            error   (str)    – set only on exception
    """
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

        return {"success": success, "state": state, "payment_id": payment_id, "error": None}

    except Exception as e:
        logger.error("PhonePe status check error for order %s: %s", order_id, e)
        return {"success": False, "state": None, "error": str(e)}


def get_phonepe_payment_status(request, order_id):
    """HTTP view: returns the current PhonePe payment status for an order.

    Accessible to:
      - the authenticated user who owns the order, OR
      - a guest whose session holds the matching guest_order_id.

    Also updates the order to Paid if PhonePe confirms COMPLETED.
    """
    try:
        order = Order.objects.get(phonepe_order_id__iexact=order_id)
    except Order.DoesNotExist:
        return JsonResponse({"error": "Order not found"}, status=404)

    # Authorization: logged-in owner OR guest session holder
    if request.user.is_authenticated:
        if order.user and order.user != request.user:
            return JsonResponse({"error": "Unauthorized"}, status=403)
    else:
        session_guest_id = str(request.session.get("guest_order_id", ""))
        if session_guest_id != str(order.id):
            return JsonResponse({"error": "Unauthorized"}, status=403)

    # If already in a terminal state, return immediately without hitting PhonePe
    if order.payment_status == "Paid":
        return JsonResponse({
            "order_id": order_id,
            "payment_status": "Paid",
            "state": "COMPLETED",
            "success": True,
        })

    status_info = _check_phonepe_payment_status(order_id)

    if status_info.get("success"):
        try:
            with transaction.atomic():
                order = Order.objects.select_for_update().get(id=order.id)
                if order.payment_status != "Paid":
                    order.payment_status = "Paid"
                    if status_info.get("payment_id"):
                        order.payment_id = status_info["payment_id"]
                    order.save(update_fields=["payment_status", "payment_id"])
                    logger.info("✅ Order #%s marked Paid via status-check view", order.id)
        except Exception as e:
            logger.error("❌ DB update failed in status-check for order #%s: %s", order.id, e)
        order.refresh_from_db()

    return JsonResponse({
        "order_id": order_id,
        "payment_status": order.payment_status,
        "state": status_info.get("state"),
        "success": status_info.get("success", False),
    })


def _verify_webhook_request(request):
    """Verify PhonePe webhook request authenticity using HTTP Basic Auth.

    PhonePe Standard Checkout v2 allows a username/password pair to be
    configured on the dashboard; it then sends them as a Basic Auth header
    on every webhook call.

    Set PHONEPE_WEBHOOK_USER and PHONEPE_WEBHOOK_PASSWORD in .env to enable
    verification.  If neither is set the check is skipped with a warning (safe
    for local dev / initial setup).

    Returns True when the request is considered authentic, False otherwise.
    """
    webhook_user = getattr(settings, "PHONEPE_WEBHOOK_USER", None) or ""
    webhook_password = getattr(settings, "PHONEPE_WEBHOOK_PASSWORD", None) or ""
    webhook_user = webhook_user.strip()
    webhook_password = webhook_password.strip()

    if not webhook_user or not webhook_password:
        logger.warning(
            "⚠️ PHONEPE_WEBHOOK_USER / PHONEPE_WEBHOOK_PASSWORD not configured — "
            "webhook auth verification is DISABLED. Set both in .env to secure the endpoint."
        )
        return True  # Permissive when no credentials are configured

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Basic "):
        logger.warning("❌ Webhook request is missing a Basic Authorization header")
        return False

    try:
        decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
        provided_user, _, provided_password = decoded.partition(":")
    except Exception as exc:
        logger.warning("❌ Could not decode webhook Authorization header: %s", exc)
        return False

    if provided_user != webhook_user or provided_password != webhook_password:
        logger.warning("❌ Webhook Authorization credentials do not match")
        return False

    return True


@csrf_exempt
def phonepe_webhook(request):
    """PhonePe Standard Checkout v2 webhook handler.

    Registered events: checkout.order.completed / checkout.order.failed / checkout.order.cancelled

    Authentication: optionally verified via HTTP Basic Auth when
    PHONEPE_WEBHOOK_USER and PHONEPE_WEBHOOK_PASSWORD are set in .env.
    """
    if request.method not in ("POST",):
        return JsonResponse({"error": "Method not allowed"}, status=405)

    # ── 0. Verify webhook authenticity ───────────────────────────────────────
    if not _verify_webhook_request(request):
        return JsonResponse({"error": "Unauthorized"}, status=401)

    # ── 1. Parse payload ─────────────────────────────────────────────────────
    try:
        body = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        logger.error("❌ Invalid JSON in webhook body")
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    logger.info("📥 PhonePe webhook received. event=%s", body.get("event", "unknown"))

    event_type = (body.get("event") or "").lower().strip()

    # Handle both flat and nested payload structures PhonePe may send
    data = body.get("payload") or body.get("data") or {}
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError as exc:
            logger.warning("⚠️ Failed to parse nested payload string: %s", exc)
            data = {}

    # ── 2. Filter to recognised events ───────────────────────────────────────
    VALID_EVENTS = {
        "checkout.order.completed": "Paid",
        "checkout.order.failed": "Failed",
        "checkout.order.cancelled": "Cancelled",
    }
    if event_type not in VALID_EVENTS:
        logger.info("🔁 Ignored unknown event: %s", event_type)
        return JsonResponse({"message": "Ignored event"}, status=200)

    new_status = VALID_EVENTS[event_type]

    # ── 3. Extract merchant order ID (handle various field names/nesting) ─────
    merchant_order_id = (
        data.get("merchantOrderId")
        or data.get("originalMerchantOrderId")
        or data.get("merchantTransactionId")
        or body.get("merchantOrderId")
        or body.get("originalMerchantOrderId")
    )
    if not merchant_order_id:
        logger.error("❗ merchantOrderId missing in webhook. body keys: %s", list(body.keys()))
        return JsonResponse({"error": "Missing merchantOrderId"}, status=400)

    logger.info("📋 Webhook event=%s merchant_order_id=%s", event_type, merchant_order_id)

    # ── 4. For Completed events: cross-check with PhonePe status API ─────────
    payment_id = None
    if new_status == "Paid":
        status_info = _check_phonepe_payment_status(merchant_order_id)

        if status_info.get("error"):
            # The status API call itself failed (network error, token expiry, etc.).
            # Return 500 so PhonePe retries the webhook delivery.
            logger.error(
                "❌ PhonePe status API call failed for %s: %s — returning 500 to trigger retry",
                merchant_order_id, status_info["error"],
            )
            return JsonResponse({"error": "Status check unavailable, please retry"}, status=500)

        if not status_info.get("success"):
            # Status API hasn't caught up yet (propagation delay / timing race).
            # PhonePe only fires checkout.order.completed for genuine payments,
            # so we trust the webhook and proceed with the DB update.
            # Execution intentionally continues here — webhook is the trusted source.
            logger.warning(
                "⚠️ Status API returned state=%s for %s, but webhook says Completed — "
                "proceeding with DB update (propagation delay / timing race)",
                status_info.get("state"), merchant_order_id,
            )

        payment_id = status_info.get("payment_id")

    # Fall back to payment details in webhook payload if not obtained from API
    if not payment_id:
        for p in (data.get("paymentDetails") or []):
            if p.get("transactionId"):
                payment_id = p["transactionId"]
                break

    # ── 5. Look up order ─────────────────────────────────────────────────────
    try:
        order = Order.objects.get(phonepe_order_id__iexact=merchant_order_id)
    except Order.DoesNotExist:
        logger.warning("❌ No order found for merchantOrderId: %s", merchant_order_id)
        return JsonResponse({"error": "Order not found"}, status=404)
    except Order.MultipleObjectsReturned:
        logger.error("❌ Multiple orders found for merchantOrderId: %s — data integrity issue", merchant_order_id)
        return JsonResponse({"error": "Ambiguous order"}, status=500)
    except Exception as e:
        logger.error("❌ DB error looking up order %s: %s", merchant_order_id, e)
        return JsonResponse({"error": "DB error"}, status=500)

    # ── 6. Idempotent DB update (select_for_update prevents race conditions) ──
    status_changed = False
    try:
        with transaction.atomic():
            order = Order.objects.select_for_update().get(id=order.id)
            if order.payment_status == new_status:
                logger.info("ℹ️ Order #%s already '%s' — no change needed", order.id, new_status)
                return JsonResponse({"message": "No change needed"}, status=200)

            previous_status = order.payment_status
            order.payment_status = new_status
            if payment_id:
                order.payment_id = payment_id
            update_fields = ["payment_status", "payment_id"]
            order.save(update_fields=update_fields)
            status_changed = True
            logger.info(
                "✅ Order #%s updated %s→%s (payment_id=%s)",
                order.id, previous_status, new_status, payment_id,
            )
    except Exception as e:
        logger.error("❌ DB update failed for order %s: %s", merchant_order_id, e)
        return JsonResponse({"error": "DB update failed"}, status=500)

    order.refresh_from_db()

    # ── 7. Send notification emails (only when status actually changed) ───────
    if status_changed:
        _send_order_status_emails(order, new_status)

    return JsonResponse({"message": "Webhook handled"}, status=200)


def _send_order_status_emails(order, new_status):
    """Send customer and admin notification emails for an order status change."""
    is_paid = (new_status == "Paid")
    is_cancelled = (new_status == "Cancelled")

    if order.email:
        try:
            items_text = "\n".join(
                f"  • {item.get('name', 'Item')} x{item.get('quantity', 1)} "
                f"— ₹{float(item.get('price', 0)) * int(item.get('quantity', 1)):.2f}"
                for item in (order.cart_items or [])
            )
        except Exception as exc:
            logger.warning("⚠️ Could not format cart items for order #%s: %s", order.id, exc)
            items_text = "(item details unavailable)"

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
                f"Regards,\nHasa Organic Seeds\n📞 7483847243 | hasafarm.com"
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
                f"Regards,\nHasa Organic Seeds"
            )
        else:
            subject = f"❌ Payment Failed — Hasa Organic Seeds Order #{order.id}"
            message = (
                f"Dear {order.full_name},\n\n"
                f"Unfortunately your payment for Order #{order.id} could not be completed.\n\n"
                f"Total Amount : ₹{order.total_amount}\n\n"
                f"Please try again at:\nhttps://hasafarm.com/cart/\n\n"
                f"If you were charged, the amount will be refunded within 5-7 business days.\n\n"
                f"Need help? Reply to this email or call 7483847243.\n\n"
                f"Regards,\nHasa Organic Seeds"
            )
        try:
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [order.email])
            logger.info("📧 Customer email sent to %s for order #%s", order.email, order.id)
        except Exception as e:
            logger.error("📧 Failed to send customer email for order #%s: %s", order.id, e)

    try:
        admin_email = getattr(settings, 'ADMIN_NOTIFICATION_EMAIL', settings.DEFAULT_FROM_EMAIL)
        admin_subject = f"[Hasafarm] Order #{order.id} — {order.payment_status}"
        admin_text_message = (
            f"Order #{order.id} — {order.payment_status}\n\n"
            f"Customer : {order.full_name}\n"
            f"Email    : {order.email}\n"
            f"Phone    : {order.phone}\n"
            f"Amount   : ₹{order.total_amount}\n"
            f"PhonePe  : {order.phonepe_order_id}\n"
            f"Txn ID : {order.payment_id or 'N/A'}\n\n"
            f"Address:\n{order.address}"
        )
        admin_html_message = render_to_string(
            "cart/emails/admin_order_status_email.html",
            {"order": order, "status": order.payment_status},
        )

        admin_message = EmailMultiAlternatives(
            admin_subject,
            admin_text_message,
            settings.DEFAULT_FROM_EMAIL,
            [admin_email],
        )
        admin_message.attach_alternative(admin_html_message, "text/html")
        admin_message.send(fail_silently=True)
        logger.info("📧 Admin email sent for order #%s", order.id)
    except Exception as e:
        logger.error("📧 Failed to send admin email for order #%s: %s", order.id, e)

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
