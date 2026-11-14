import os
ROOT = os.path.dirname(os.path.abspath(__file__))

def patch(path, label, old, new):
    full = os.path.join(ROOT, path)
    if not os.path.exists(full):
        print(f"  SKIP (not found): {label}"); return
    txt = open(full, encoding="utf-8").read()
    if old not in txt:
        print(f"  SKIP (pattern missing): {label}"); return
    open(full, "w", encoding="utf-8").write(txt.replace(old, new, 1))
    print(f"  OK  {label}")

print("\naccounts/templates/accounts/emails/winback_email.html")
patch(
    "accounts/templates/accounts/emails/winback_email.html",
    "Use dynamic coupon_code from context, not hardcoded COMEBACK10",
    '''    <p>Here's a little something to bring you back:</p>
    <p style="font-size:18px; font-weight:800; color:#f57c00;">Use code <span style="background:#fff3e0; padding:4px 10px; border-radius:6px;">COMEBACK10</span> for 10% off your next order</p>''',
    '''    {% if coupon_code %}
    <p>Here's a little something to bring you back:</p>
    <p style="font-size:18px; font-weight:800; color:#f57c00;">Use code <span style="background:#fff3e0; padding:4px 10px; border-radius:6px;">{{ coupon_code }}</span> for 10% off your next order</p>
    {% else %}
    <p>We've restocked our most popular seeds this season — come back and explore what's new.</p>
    {% endif %}''',
)

print("\ncart/templates/cart/cart.html")

# Remove orphaned debug variable
patch(
    "cart/templates/cart/cart.html",
    "Remove orphaned debug variable outside loop",
    "<p>{{ item.seed.image_url }}</p>\n",
    "",
)

# Fix nullable image crash
patch(
    "cart/templates/cart/cart.html",
    "Guard image.url against null image",
    '                    <img src="{{ item.seed.image.url }}" alt="{{ item.seed.name }}" width="80" height="80" style="border-radius: 5px;">',
    '                    {% if item.seed.image %}<img src="{{ item.seed.image.url }}" alt="{{ item.seed.name }}" width="80" height="80" style="border-radius: 5px;">{% endif %}',
)

print("\norders/templates/orders/my_orders.html")

# Fix GET reorder -> POST form
patch(
    "orders/templates/orders/my_orders.html",
    "Reorder: GET link -> POST form (session-mutating action)",
    '<a href="{% url \'reorder\' order.id %}" class="reorder">Reorder</a>',
    '''<form method="post" action="{% url 'reorder' order.id %}" style="display:inline;">
                        {% csrf_token %}
                        <button type="submit" class="reorder" style="cursor:pointer;border:none;padding:10px 18px;border-radius:8px;background:#2ecc71;color:white;font-weight:500;">Reorder</button>
                    </form>''',
)

print("\nDone.\n")
