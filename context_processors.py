# This file is unused — cart counts are injected directly in each view.
# Kept as a placeholder so any template reference to cart_count still works
# safely without raising an error if wired up accidentally.

def cart_count(request):
    """Safe no-op context processor. Cart count is managed via session in views."""
    cart = request.session.get("cart", {})
    return {"cart_count": len(cart)}
