"""
Create or update a coupon code.

    python manage.py create_coupon COMEBACK10 --percent 10 --days 7

Safe to re-run: if the code already exists, it updates percent_off/valid_until/active
instead of erroring.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils.timezone import now

from orders.models import Coupon


class Command(BaseCommand):
    help = "Create or update a promo coupon code."

    def add_arguments(self, parser):
        parser.add_argument("code", type=str, help="Coupon code, e.g. COMEBACK10")
        parser.add_argument("--percent", type=int, required=True, help="Percent off, e.g. 10")
        parser.add_argument("--days", type=int, required=True, help="Number of days from now until it expires")
        parser.add_argument("--inactive", action="store_true", help="Create it disabled (active=False)")

    def handle(self, *args, **options):
        code = options["code"].strip().upper()
        percent = options["percent"]
        days = options["days"]

        if not (0 < percent <= 100):
            raise CommandError("--percent must be between 1 and 100")
        if days <= 0:
            raise CommandError("--days must be positive")

        valid_until = now() + timedelta(days=days)

        coupon, created = Coupon.objects.update_or_create(
            code=code,
            defaults={
                "percent_off": percent,
                "valid_until": valid_until,
                "active": not options["inactive"],
            },
        )

        verb = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(
            f"{verb} coupon {coupon.code}: {coupon.percent_off}% off, "
            f"active={coupon.active}, valid until {coupon.valid_until:%Y-%m-%d %H:%M %Z}"
        ))
