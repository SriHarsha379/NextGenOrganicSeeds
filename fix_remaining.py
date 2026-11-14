import os
ROOT = os.path.dirname(os.path.abspath(__file__))

def patch(path, label, old, new):
    full = os.path.join(ROOT, path)
    txt = open(full, encoding="utf-8").read()
    if old not in txt:
        print(f"  WARNING PATTERN MISSING: {label}")
        return
    open(full, "w", encoding="utf-8").write(txt.replace(old, new, 1))
    print(f"  OK  {label}")

print("\ncart/views.py")

patch(
    "cart/views.py",
    "Recompute total server-side from DB prices",
    '        postal_charge = Decimal("80.00")\n        try:\n            base_amount = Decimal(str(data["total_amount"]))\n            if base_amount <= 0:\n                raise ValueError("Invalid total_amount")\n        except (ValueError, TypeError, KeyError):\n            return JsonResponse({"error": "Invalid amount format"}, status=400)',
    '        # Recompute from DB — never trust client total_amount\n        db_subtotal = Decimal("0.00")\n        for _item in data["cart_items"]:\n            try:\n                _seed = Seed.objects.get(id=_item["id"])\n            except Seed.DoesNotExist:\n                return JsonResponse({"error": f\'Item not found: {_item.get("id")}\'}, status=400)\n            _qty = int(_item.get("quantity", 1))\n            if _qty <= 0:\n                return JsonResponse({"error": f"Invalid quantity for {_seed.name}"}, status=400)\n            db_subtotal += _seed.price * _qty\n        if db_subtotal <= 0:\n            return JsonResponse({"error": "Cart is empty"}, status=400)\n        base_amount = db_subtotal\n        postal_charge = Decimal("0.00") if db_subtotal >= Decimal("499.00") else Decimal("80.00")',
)

patch(
    "cart/views.py",
    "Fix retry_payment: allow authenticated owner",
    '    # 🔐 Guest session validation\n    session_guest_id = str(request.session.get("guest_order_id"))\n    if session_guest_id != str(order.id):\n        return HttpResponseForbidden("Unauthorized access to this guest order.")\n\n    # ✅ Retry logic\n    if order.payment_status != "Paid":\n        return redirect(order.payment_link or "home")\n\n    # Already paid — show success\n    return redirect("order_success", phonepe_order_id=order.phonepe_order_id)',
    '    is_owner = request.user.is_authenticated and order.user == request.user\n    is_guest = str(request.session.get("guest_order_id", "")) == str(order.id)\n    if not (is_owner or is_guest):\n        return HttpResponseForbidden("Unauthorized access to this order.")\n    if order.payment_status == "Paid":\n        return redirect("order_success", phonepe_order_id=order.phonepe_order_id)\n    return redirect(order.payment_link or "home")',
)

print("\nDone.\n")
