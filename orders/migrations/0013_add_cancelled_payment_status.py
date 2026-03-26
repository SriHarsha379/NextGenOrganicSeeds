from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0012_order_is_printed'),
    ]

    operations = [
        migrations.AlterField(
            model_name='order',
            name='payment_status',
            field=models.CharField(
                choices=[
                    ('Pending', 'Pending'),
                    ('Paid', 'Paid'),
                    ('Failed', 'Failed'),
                    ('Cancelled', 'Cancelled'),
                    ('Refunded', 'Refunded'),
                ],
                default='Pending',
                max_length=20,
            ),
        ),
    ]
