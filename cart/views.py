from django.db import transaction
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

            # Fixed postal charges = ₹80
            postal_charge = 80

            # Calculate final amount including postal charges
            base_total = float(data["total_amount"])
            final_amount = base_total + postal_charge

            with transaction.atomic():
                order = Order.objects.create(
                    user=request.user,
                    full_name=data["full_name"],
                    email=data["email"],
                    phone=data["phone"],
                    address=address,
                    cart_items=data["cart_items"],
                    total_quantity=data["total_quantity"],
                    total_amount=final_amount,  # total + postal charges
                    postal_charge=postal_charge,  # store postal charges separately
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

                # Prepare order payload for Cashfree API
                order_payload = {
                    "order_id": str(order.id),  # Use Django Order ID as unique order_id
                    "order_amount": str(order.total_amount),
                    "order_currency": "INR",
                    "customer_details": {
                        "customer_id": str(request.user.id),
                        "customer_email": order.email,
                        "customer_phone": order.phone
                    },
                    "order_meta": {
                        "return_url": "https://hasafarm.com/order-success/?order_id={order_id}",
                        "notify_url": "https://hasafarm.com/webhooks/cashfree"
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

                # Store the order_id returned by Cashfree in your DB
                order.cf_order_id = order_resp_json.get("order_id")  # **important fix**
                order.order_token = order_resp_json.get("order_token")
                order.payment_link = order_resp_json.get("payment_link")
                order.save()

                # Clear user cart session
                request.session["cart"] = {}
                request.session.modified = True

                return JsonResponse({
                    "message": "Order placed successfully!",
                    "order_id": order.id,
                    "payment_link": order.payment_link,
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

    order = get_object_or_404(Order, cf_order_id=order_id)

    headers = {
        "Content-Type": "application/json",
        "X-Client-Id": settings.CASHFREE_APP_ID,
        "X-Client-Secret": settings.CASHFREE_SECRET_KEY,
        "x-api-version": "2022-01-01"
    }

    response = requests.get(
        f"https://api.cashfree.com/pg/orders/{order.cf_order_id}",
        headers=headers
    )

    if response.status_code == 200:
        data = response.json()
        cashfree_status = data.get("order_status")
        if cashfree_status and cashfree_status != order.payment_status:
            order.payment_status = cashfree_status
            order.save()
    else:
        print("Error fetching order status from Cashfree:", response.text)

    if order.payment_status == "PAID" or order.payment_status == "SUCCESS":
        message_title = "Payment Successful!"
        message_body = f"Thank you for your order #{order.id}. We've received your payment."
        btn_text = "Continue Shopping"
        btn_link = "/seeds/"  # ← ✅ Updated to existing path
    elif order.payment_status == "FAILED":
        message_title = "Payment Failed"
        message_body = "Unfortunately, your payment failed. Please try again."
        btn_text = "Retry Payment"
        btn_link = f"/checkout/?order_id={order.cf_order_id}"
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
def cashfree_webhook_view(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid method"}, status=405)

    try:
        payload = request.body.decode("utf-8")
        data = json.loads(payload)

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
            return JsonResponse({"error": "Missing order_id or status"}, status=400)

        try:
            order = Order.objects.get(cf_order_id=cf_order_id)
        except Order.DoesNotExist:
            return JsonResponse({"error": "Order not found"}, status=404)

        if order.payment_status == "Paid":
            return HttpResponse("Already processed", status=200)

        if order_status.upper() == "PAID":
            order.payment_status = "Paid"
            order.save()

            # Prepare order details for email
            try:
                items = order.cart_items
                ordered_items = ""
                for item in items:
                    name = item.get("name", "Unknown")
                    qty = item.get("quantity", 1)
                    price = item.get("total_price", "N/A")
                    ordered_items += f"{name} - Qty: {qty} - ₹{price}\n"
            except Exception:
                ordered_items = "Unable to retrieve order items."

            email_subject = f"✅ Your Order #{order.id} is Confirmed - Hasa Farm"
            email_message = f"""
Hi {order.full_name},

Thank you for your purchase! We have received your payment for Order #{order.id}.

Order Summary:
{ordered_items}

Total Quantity: {order.total_quantity}
Postal Charges: ₹{order.postal_charge}
Total Amount Paid: ₹{order.total_amount}

We will notify you once your order is shipped.

Regards,
Hasa Farm Team
            """.strip()

            try:
                send_mail(
                    subject=email_subject,
                    message=email_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[order.email, "contact@hasafarm.com"],
                    fail_silently=False
                )
            except Exception as e:
                print("Email send failed:", e)

            return HttpResponse("Payment successful", status=200)

        elif order_status.upper() == "FAILED":
            order.payment_status = "Failed"
            order.save()
            return HttpResponse("Payment failed", status=200)

        else:
            return JsonResponse({"error": "Unhandled status"}, status=400)

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except Exception as e:
        print("Webhook error:", e)
        return JsonResponse({"error": "Server error"}, status=500)

def send_order_confirmation_email(order):
    try:
        items = order.cart_items
        ordered_items = ""
        for item in items:
            name = item.get("name", "Unknown")
            qty = item.get("quantity", 1)
            price = item.get("total_price", "N/A")
            ordered_items += f"{name} - Qty: {qty} - ₹{price}\n"
    except Exception:
        ordered_items = "Unable to retrieve order items."

    email_subject = f"✅ Your Order #{order.id} is Confirmed - Hasa Farm"
    email_message = f"""
Hi {order.full_name},

Thank you for your purchase! We have received your payment for Order #{order.id}.

Order Summary:
{ordered_items}

Total Quantity: {order.total_quantity}
Postal Charges: ₹{order.postal_charge}
Total Amount Paid: ₹{order.total_amount}

We will notify you once your order is shipped.

Regards,
Hasa Farm Team
    """.strip()

    send_mail(
        subject=email_subject,
        message=email_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[order.email, "contact@hasafarm.com"],
        fail_silently=False,
    )

def verify_cashfree_payment(cf_order_id: str):
    url = f"{CASHFREE_ORDER_API_URL}{cf_order_id}"
    headers = {
        "Content-Type": "application/json",
        "X-Client-Id": CASHFREE_APP_ID,
        "X-Client-Secret": CASHFREE_SECRET_KEY,
        "x-api-version": "2022-01-01"
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"❌ Error verifying Cashfree order {cf_order_id}: {e}")
        return None


def verify_pending_orders():
    pending_orders = Order.objects.filter(payment_status="Pending")
    updated_count = 0
    for order in pending_orders:
        if order.cf_order_id:
            result = verify_cashfree_payment(order.cf_order_id)
            if result and result.get("order_status") == "PAID":
                order.payment_status = "Paid"
                order.payment_id = result.get("payment_id") or order.payment_id
                order.save()
                send_order_confirmation_email(order)  # Send mail on update
                print(f"✅ Order #{order.id} updated to Paid and email sent.")
                updated_count += 1
            else:
                status = result.get("order_status") if result else "No result"
                print(f"⏳ Order #{order.id} still pending or failed: {status}")
    print(f"Total orders updated: {updated_count}")
    return updated_count
