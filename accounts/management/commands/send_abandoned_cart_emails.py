"""
Emails customers whose most recent order never completed payment (Pending/Failed/
Cancelled), with a link that restores their exact cart and drops them at checkout.

Only targets each customer's MOST RECENT order — if they've since placed and paid for
a newer order, they're correctly skipped (already converted).

    python manage.py send_abandoned_cart_emails --dry-run
    python manage.py send_abandoned_cart_emails --hours 3 --cooldown 3 --limit 50
"""
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils.timezone import now

from accounts.models import MarketingEmailPreference, CampaignSend
from accounts.views import make_unsubscribe_token
from cart.views import make_resume_cart_token
from orders.models import Order

CAMPAIGN_NAME = "abandoned_cart"
UNPAID_STATUSES = ("Pending", "Failed", "Cancelled")


class Command(BaseCommand):
    help = "Email customers who started checkout but never paid, with a link to resume their cart."

    def add_arguments(self, parser):
        parser.add_argument(
            "--hours", type=int, default=3,
            help="Only target orders at least this many hours old (avoids emailing someone still mid-checkout). Default: 3.",
        )
        parser.add_argument(
            "--cooldown", type=int, default=3,
            help="Don't re-send to someone already emailed this campaign within this many days. Default: 3.",
        )
        parser.add_argument("--limit", type=int, default=None, help="Cap how many emails to send this run.")
        parser.add_argument("--dry-run", action="store_true", help="Preview without sending.")

    def handle(self, *args, **options):
        cutoff = now() - timedelta(hours=options["hours"])
        cooldown_cutoff = now() - timedelta(days=options["cooldown"])
        limit = options["limit"]
        dry_run = options["dry_run"]

        # Latest order per email, across ALL statuses (so we can tell if they later paid).
        latest_order_by_email = {}
        for order in Order.objects.exclude(email="").order_by("email", "-created_at"):
            email = order.email.strip().lower()
            if email not in latest_order_by_email:
                latest_order_by_email[email] = order

        targets = [
            o for o in latest_order_by_email.values()
            if o.payment_status in UNPAID_STATUSES and o.created_at <= cutoff
        ]
        targets.sort(key=lambda o: o.created_at)

        self.stdout.write(f"Found {len(targets)} customers with an unpaid order {options['hours']}+ hours old.")

        sent = skipped_unsub = skipped_cooldown = 0

        for order in targets:
            if limit is not None and sent >= limit:
                self.stdout.write(self.style.WARNING(f"Reached --limit {limit}, stopping."))
                break

            email = order.email.strip().lower()
            pref, _ = MarketingEmailPreference.objects.get_or_create(email=email)
            if pref.unsubscribed:
                skipped_unsub += 1
                continue

            log = CampaignSend.objects.filter(email=email, campaign=CAMPAIGN_NAME).first()
            if log and log.sent_at >= cooldown_cutoff:
                skipped_cooldown += 1
                continue

            if dry_run:
                self.stdout.write(f"  [DRY RUN] would email {email} (order #{order.id}, {order.payment_status})")
                sent += 1
                continue

            self._send(order, email)
            sent += 1

        self.stdout.write(self.style.SUCCESS(
            f"Done. Sent: {sent}  Skipped (unsubscribed): {skipped_unsub}  Skipped (cooldown): {skipped_cooldown}"
        ))

    def _send(self, order, email):
        resume_token = make_resume_cart_token(order)
        unsub_token = make_unsubscribe_token(email)
        context = {
            "name": order.full_name.split(" ")[0] if order.full_name else "there",
            "items": order.cart_items,
            "resume_url": f"{settings.SITE_URL}/cart/resume/{resume_token}/",
            "unsubscribe_url": f"{settings.SITE_URL}/accounts/unsubscribe/{unsub_token}/",
        }
        html_message = render_to_string("accounts/emails/abandoned_cart_email.html", context)
        plain_message = strip_tags(html_message)

        try:
            send_mail(
                subject="You left something in your cart 🌱",
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                html_message=html_message,
                fail_silently=False,
            )
            CampaignSend.objects.update_or_create(email=email, campaign=CAMPAIGN_NAME)
            self.stdout.write(f"  ✅ sent to {email}")
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"  ❌ failed for {email}: {e}"))
