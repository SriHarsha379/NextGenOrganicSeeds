from django.http import JsonResponse

def cart_count(request):
    cart = request.session.get('cart', {})
    cart_count = sum(cart.values())  # Assuming you store quantities in the cart
    return JsonResponse({'cart_count': cart_count})
