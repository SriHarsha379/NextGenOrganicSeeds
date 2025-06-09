import csv
import io
import json
from collections import Counter
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.conf import settings
from django.views.decorators.csrf import csrf_protect

from cart.models import Cart
from .models import  Order
from django.core.mail import send_mail
from django.utils.crypto import get_random_string
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from io import BytesIO, StringIO
from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors
import os
from django.contrib.admin.views.decorators import staff_member_required

# @login_required
# def checkout(request):
#     cart_items = Cart.objects.filter(user=request.user)
#     total_amount = sum(item.total_price() for item in cart_items)
#
#     if request.method == "POST":
#         full_name = request.POST["full_name"]
#         email = request.POST["email"]
#         phone = request.POST["phone"]
#         address = request.POST["address"]
#
#         with transaction.atomic():
#             # Store all cart items inside `cart_items` JSONField
#             order_data = [
#                 {"seed": item.seed.name, "quantity": item.quantity, "price": item.total_price()}
#                 for item in cart_items
#             ]
#             order_id = get_random_string(10).upper()  # Generate a unique order ID
#
#             order = Order.objects.create(
#                 user=request.user,
#                 full_name=full_name,
#                 email=email,
#                 phone=phone,
#                 address=address,
#                 cart_items=order_data,  # Store cart as JSON
#                 total_quantity=sum(item.quantity for item in cart_items),
#                 total_amount=total_amount,
#                 payment_status="Pending",
#                 payment_id=order_id,  # Temporary order ID
#             )
#
#             cart_items.delete()  # Clear cart after placing the order
#
#         # Send order confirmation email
#         send_mail(
#             "Order Confirmation - Next Gen Organic Seeds",
#             f"Hello {full_name},\n\nYour order has been placed successfully!\n\nOrder ID: {order_id}\nTotal: ₹{total_amount}\n\nThank you for shopping with us!",
#             "yourstore@example.com",
#             [email],
#             fail_silently=False,
#         )
#
#         return redirect("order_success", order_id=order_id)  # Redirect to success page
#
#     return render(request, "orders/checkout.html", {"cart_items": cart_items, "total_amount": total_amount})


@login_required
def upi_payment(request):
    upi_link = request.GET.get("upi_link")
    if not upi_link:
        return redirect("checkout")  # Redirect back if no UPI link found
    return render(request, "orders/upi_payment.html", {"upi_link": upi_link})


@login_required
def payment_success(request):
    # Here, you should verify the payment via UPI API before updating order status
    orders = Order.objects.filter(user=request.user, status="Pending")
    orders.update(status="Completed")
    return render(request, "orders/payment_success.html")


@login_required
def my_orders(request):
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'orders/my_orders.html', {
        'orders': orders,
        'MEDIA_URL': settings.MEDIA_URL
    })


@login_required
def download_invoice(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)

    # Clean address to remove empty parts causing double commas
    raw_address = order.address or ""
    address_parts = [part.strip() for part in raw_address.split(",")]
    clean_address = ", ".join([part for part in address_parts if part])

    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    y = height - 50

    # Logo
    logo_path = os.path.join('E:/imp/python project/NextGenOrganicSeeds/static/images/hasa_organic_seeds.png')
    if os.path.exists(logo_path):
        p.drawImage(logo_path, (width - 130) / 2, y - 40, width=130, height=40, mask='auto')

    # Title
    p.setFont("Helvetica-Bold", 18)
    p.drawCentredString(width / 2, y - 70, f"INVOICE - Order #{order.id}")

    # Customer & Order Details
    p.setFont("Helvetica", 12)
    text_start_y = y - 110
    line_height = 18

    customer_lines = [
        f"Name: {order.full_name}",
        f"Email: {order.email}",
        f"Phone: {order.phone}",
        f"Address: {clean_address}",  # use cleaned address here
        f"Order Date: {order.created_at.strftime('%d %b %Y, %I:%M %p')}",
        f"Payment Status: {order.payment_status}",
    ]

    for i, line in enumerate(customer_lines):
        p.drawString(40, text_start_y - (i * line_height), line)

    # Table Data
    data = [['Item', 'Quantity', 'Price (INR)', 'Total (INR)']]
    for item in order.cart_items:
        name = item.get("name", "")
        qty = item.get("quantity", 1)
        price = item.get("price", 0)
        total = qty * price
        data.append([name, qty, f"{price:.2f}", f"{total:.2f}"])

    data.append(["", "", "Subtotal", f"{order.total_amount:.2f}"])
    data.append(["", "", "Postal Charge", f"{order.postal_charge:.2f}"])
    grand_total = order.total_amount + order.postal_charge
    data.append(["", "", "Grand Total", f"INR {grand_total:.2f}"])

    # Table Styling
    table = Table(data, colWidths=[220, 80, 100, 100])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f0f0f0')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#333333')),
        ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('TOPPADDING', (0, 0), (-1, 0), 10),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
        ('FONTNAME', (-2, -3), (-1, -1), 'Helvetica-Bold'),
        ('BACKGROUND', (-2, -3), (-1, -1), colors.HexColor("#e8f6f3")),
    ]))

    # Position table
    table.wrapOn(p, width, height)
    table.drawOn(p, 40, text_start_y - 220)

    # Footer
    p.setFont("Helvetica-Oblique", 9)
    p.setFillColor(colors.grey)
    p.drawCentredString(width / 2, 40, "Thank you for shopping with Hasa Farm – We value your trust!")

    p.showPage()
    p.save()
    buffer.seek(0)

    return HttpResponse(buffer, content_type='application/pdf', headers={
        'Content-Disposition': f'attachment; filename="Invoice_Order_{order.id}.pdf"'
    })



@login_required
def reorder(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    # order.cart_items is a list of items; convert to dict with seed IDs as keys
    cart_dict = {}
    for item in order.cart_items:
        # Assuming each item has an 'id' or 'seed_id' field
        seed_id = str(item.get('id') or item.get('seed_id'))
        if seed_id:
            cart_dict[seed_id] = {
                'quantity': item.get('quantity', 1),
                # add other cart item details if needed
            }
    request.session['cart'] = cart_dict
    request.session.modified = True  # mark session as modified to save changes
    return redirect('view_cart')


def is_admin(user):
    return user.is_superuser

@staff_member_required
@csrf_protect
def parse_raw_order_data(request):
    extracted_orders = []
    error = None

    if request.method == "POST":
        raw_data = request.POST.get("raw_data")
        if raw_data:
            try:
                f = StringIO(raw_data)
                reader = csv.reader(f, delimiter='\t')

                for row in reader:
                    try:
                        full_name = row[1].strip('"')
                        phone = row[3].strip('"')
                        address = row[4].strip('"')
                        address_lines = [line.strip() for line in address.split(",")]

                        extracted_orders.append({
                            "name": full_name,
                            "phone": phone,
                            "address": address,
                            "address_lines": address_lines,
                        })
                    except Exception as row_error:
                        continue  # Skip malformed rows

            except Exception as e:
                error = f"Failed to parse data: {e}"

    return render(request, "orders/parse_order.html", {
        "extracted_orders": extracted_orders,
        "error": error,
    })

@staff_member_required
def bulk_item_extractor(request):
    items = []
    pick_counter = Counter()
    order_line_summaries = {}
    errors = []

    if request.method == "POST":
        raw_data = request.POST.get("raw_data", "")
        reader = csv.reader(io.StringIO(raw_data), delimiter="\t")

        for line_no, row in enumerate(reader, start=1):
            if len(row) < 6:
                errors.append(f"Line {line_no}: not enough columns.")
                continue

            order_id = row[0].strip()
            name = row[1].strip()
            cart_blob = row[5].strip()

            # Clean the JSON string
            if cart_blob.startswith('"') and cart_blob.endswith('"'):
                cart_blob = cart_blob[1:-1].replace('""', '"')

            try:
                cart = json.loads(cart_blob)
            except json.JSONDecodeError as exc:
                errors.append(f"Line {line_no}: JSON error – {exc}")
                continue

            summary_parts = []
            for prod in cart:
                item_id = prod["id"]
                name_item = prod["name"]
                qty = int(prod["quantity"])
                price = float(prod["price"])
                total = float(prod.get("total_price", price * qty))

                items.append([order_id, item_id, name_item, qty, price, total])
                pick_counter[name_item] += qty
                summary_parts.append(f"{name_item} ×{qty}")

            # 🔧 Use order_id + name as key for summary
            display_key = f"{order_id} - {name}" if name else order_id
            order_line_summaries[display_key] = ", ".join(summary_parts)

        if "download_items" in request.POST:
            return _csv_response("items_export.csv",
                                 ["order_id", "sku", "name", "qty", "price", "total"],
                                 items)

        if "download_pick" in request.POST:
            pick_rows = [[name, qty] for name, qty in pick_counter.items()]
            return _csv_response("pick_list.csv", ["name", "total_qty"], pick_rows)

    context = {
        "items": items,
        "pick_list": pick_counter.items(),
        "order_lines": order_line_summaries,
        "errors": errors,
    }
    return render(request, "orders/bulk_item_extractor.html", context)



def _csv_response(filename, headers, rows):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow(headers)
    writer.writerows(rows)
    return response
