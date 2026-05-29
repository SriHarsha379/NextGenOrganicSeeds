from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from orders.models import Order


class BulkPrintOrdersTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='password123',
        )
        self.client.force_login(self.admin_user)

    def create_order(self, **overrides):
        defaults = {
            'full_name': 'Test Customer',
            'email': 'customer@example.com',
            'phone': '9999999999',
            'address': 'Test address',
            'cart_items': [
                {'name': 'Tomato Seeds', 'quantity': 2, 'price': 45},
                {'name': 'Chilli Seeds', 'quantity': 1, 'price': 35},
            ],
            'total_amount': '125.00',
            'postal_charge': '45.00',
            'payment_status': 'Paid',
        }
        defaults.update(overrides)
        return Order.objects.create(**defaults)

    def test_bulk_print_redirects_without_selected_orders(self):
        response = self.client.get(reverse('adminpanel:bulk_print_orders'))

        self.assertRedirects(response, '/admin/orders/?bulk_print_error=1')

    def test_bulk_print_groups_orders_by_requested_page_size(self):
        first_order = self.create_order(full_name='First Customer')
        second_order = self.create_order(full_name='Second Customer')
        third_order = self.create_order(full_name='Third Customer')

        response = self.client.get(
            reverse('adminpanel:bulk_print_orders'),
            {'order_ids': [first_order.id, second_order.id, third_order.id], 'per_page': 2},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'adminpanel/bulk_order_print.html')
        self.assertEqual(response.context['orders_per_page'], 2)
        self.assertEqual(response.context['selected_count'], 3)
        self.assertEqual(len(response.context['order_pages']), 2)
        self.assertEqual(first_order.total_quantity, 3)
        self.assertEqual(response.context['order_pages'][0], [first_order, second_order])
        self.assertEqual(response.context['order_pages'][1], [third_order])

    def test_bulk_print_falls_back_to_two_per_page_for_invalid_value(self):
        first_order = self.create_order(full_name='First Customer')
        second_order = self.create_order(full_name='Second Customer')
        third_order = self.create_order(full_name='Third Customer')

        response = self.client.get(
            reverse('adminpanel:bulk_print_orders'),
            {'order_ids': [first_order.id, second_order.id, third_order.id], 'per_page': 9},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['orders_per_page'], 2)
        self.assertEqual(len(response.context['order_pages']), 2)
