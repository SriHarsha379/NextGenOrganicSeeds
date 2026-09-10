"""
Sends a "come back and shop again" email to customers who haven't ordered
recently, and haven't already been sent this campaign within the cooldown
window. Designed to be run on a schedule (cron) — see README section added
to the project, or run manually:

    python manage.py send_winback_emails
    python manage.py send_winback_emails --days 30 --cooldown 45 --dry-run
    python manage.py send_winback_emails --limit 50   # throttle a big first run

Safe to run daily: customers are only ever emailed once per --cooldown period,
and anyone who unsubscribed (via the link in the email) is skipped for good.
"""
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils.timezone import now

from accounts.models import MarketingEmailPreference
from accounts.views import make_unsubscribe_token
from orders.models import Order


class Command(BaseCommand):
    help = "Email customers who haven't ordered in a while, encouraging them to come back and shop again."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days", type=int, default=30,
            help="Only target customers whose most recent order is at least this many days old (default: 30).",
        )
        parser.add_argument(
            "--cooldown", type=int, default=30,
            help="Don't re-send to someone who already got a win-back email within this many days (default: 30).",
        )
        parser.add_argument(
            "--limit", type=int, default=None,
            help="Optional cap on how many emails to send in this run (useful for a first backfill run).",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Print who WOULD be emailed without actually sending anything.",
        )

    def handle(self, *args, **options):
        days = options["days"]
        cooldown_days = options["cooldown"]
        limit = options["limit"]
        dry_run = options["dry_run"]

        cutoff = now() - timedelta(days=days)
        cooldown_cutoff = now() - timedelta(days=cooldown_days)

        # Only consider customers who have paid at least once — no point win-backing
        # someone who never completed a purchase.
        paid_orders = Order.objects.filter(payment_status="Paid")

        # Latest paid order per email address.
        latest_order_by_email = {}
        for order in paid_orders.order_by("email", "-created_at"):
            email = (order.email or "").strip().lower()
            if not email:
                continue
            if email not in latest_order_by_email:
                latest_order_by_email[email] = order

        targets = [
            order for order in latest_order_by_email.values()
            if order.created_at <= cutoff
        ]
        targets.sort(key=lambda o: o.created_at)  # most-inactive-first

        self.stdout.write(f"Found {len(targets)} customers inactive for {days}+ days.")

        sent_count = 0
        skipped_unsubscribed = 0
        skipped_cooldown = 0

        for order in targets:
            if limit is not None and sent_count >= limit:
                self.stdout.write(self.style.WARNING(f"Reached --limit {limit}, stopping."))
                break

            email = order.email.strip().lower()
            pref, _ = MarketingEmailPreference.objects.get_or_create(email=email)

            if pref.unsubscribed:
                skipped_unsubscribed += 1
                continue

            if pref.last_campaign_sent_at and pref.last_campaign_sent_at >= cooldown_cutoff:
                skipped_cooldown += 1
                continue

            if dry_run:
                self.stdout.write(f"  [DRY RUN] would email {email} (last order {order.created_at:%Y-%m-%d})")
                sent_count += 1
                continue

            self._send_winback_email(order, pref)
            sent_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"Done. Sent: {sent_count}  Skipped (unsubscribed): {skipped_unsubscribed}  "
            f"Skipped (cooldown): {skipped_cooldown}"
        ))

    def _send_winback_email(self, order, pref):
        email = pref.email
        token = make_unsubscribe_token(email)
        context = {
            "name": order.full_name.split(" ")[0] if order.full_name else "there",
            "shop_url": f"{settings.SITE_URL}/seeds/",
            "unsubscribe_url": f"{settings.SITE_URL}/accounts/unsubscribe/{token}/",
        }
        html_message = render_to_string("accounts/emails/winback_email.html", context)
        plain_message = strip_tags(html_message)

        try:
            send_mail(
                subject="We miss you at Hasa Farm 🌱 Here's 10% off your next order",
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                html_message=html_message,
                fail_silently=False,
            )
            pref.last_campaign_sent_at = now()
            pref.last_campaign_name = "winback"
            pref.save(update_fields=["last_campaign_sent_at", "last_campaign_name"])
            self.stdout.write(f"  ✅ sent to {email}")
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"  ❌ failed for {email}: {e}"))
