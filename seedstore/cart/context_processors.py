from django.shortcuts import get_object_or_404
from django.contrib.sessions.models import Session

def cart_count(request):
    cart = request.session.get("cart", {})
    print("🔄 Cart Count from Context Processor:", len(cart))  # Debugging
    return {"cart_count": len(cart)}

