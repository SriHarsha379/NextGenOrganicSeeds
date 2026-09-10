"""
Sends a seasonal announcement to every customer who has ever paid for an order
(excluding anyone who ordered very recently — they don't need a nudge).

Content comes from seasonal_campaign.json at the project root — edit that file
whenever the featured season/products change, NOT this command. That's what lets
this run unattended from cron: the schedule is automatic, the season config is
whatever you last saved.

Each person gets at most ONE email per distinct "season" value in the config —
re-running with the same season is a safe no-op for anyone already sent. Changing
the season name in the JSON (e.g. "Monsoon 2026" -> "Winter 2026") gives everyone
a fresh email next quarter.

    python manage.py send_seasonal_email --dry-run
    python manage.py send_seasonal_email --limit 20
"""
import json
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils.timezone import now

from accounts.models import MarketingEmailPreference, CampaignSend
from accounts.views import make_unsubscribe_token
from orders.models import Order

CONFIG_PATH = Path(settings.BASE_DIR) / "seasonal_campaign.json"


class Command(BaseCommand):
    help = "Send the current seasonal announcement (from seasonal_campaign.json) to all paying customers."

    def add_arguments(self, parser):
        parser.add_argument(
            "--min-days-inactive", type=int, default=14,
            help="Skip anyone whose most recent PAID order is more recent than this many days — "
                 "they already know about you, no need to nudge them. Default: 14.",
        )
        parser.add_argument("--limit", type=int, default=None, help="Cap how many emails to send this run.")
        parser.add_argument("--dry-run", action="store_true", help="Preview without sending.")

    def handle(self, *args, **options):
        if not CONFIG_PATH.exists():
            raise CommandError(
                f"No seasonal_campaign.json found at {CONFIG_PATH}. "
                "Create it with 'season', 'subject', and 'highlight' keys before running this."
            )
        try:
            config = json.loads(CONFIG_PATH.read_text())
            season = config["season"]
            subject = config["subject"]
            highlight = config["highlight"]
        except (json.JSONDecodeError, KeyError) as e:
            raise CommandError(f"seasonal_campaign.json is malformed: {e}")

        campaign_name = f"seasonal_{season}"
        cutoff = now() - timedelta(days=options["min_days_inactive"])
        limit = options["limit"]
        dry_run = options["dry_run"]

        # Latest PAID order per email — this defines "a customer who's with us".
        latest_paid_by_email = {}
        for order in Order.objects.filter(payment_status="Paid").exclude(email="").order_by("email", "-created_at"):
            email = order.email.strip().lower()
            if email not in latest_paid_by_email:
                latest_paid_by_email[email] = order

        targets = [o for o in latest_paid_by_email.values() if o.created_at <= cutoff]
        targets.sort(key=lambda o: o.created_at)

        self.stdout.write(
            f"Season: {season!r}  |  {len(targets)} customers eligible "
            f"(last paid order {options['min_days_inactive']}+ days ago)."
        )

        sent = skipped_unsub = skipped_already_this_season = 0

        for order in targets:
            if limit is not None and sent >= limit:
                self.stdout.write(self.style.WARNING(f"Reached --limit {limit}, stopping."))
                break

            email = order.email.strip().lower()
            pref, _ = MarketingEmailPreference.objects.get_or_create(email=email)
            if pref.unsubscribed:
                skipped_unsub += 1
                continue

            # No time-based cooldown here — a season only changes a few times a year,
            # so "already sent for THIS season" is a permanent skip until the config changes.
            if CampaignSend.objects.filter(email=email, campaign=campaign_name).exists():
                skipped_already_this_season += 1
                continue

            if dry_run:
                self.stdout.write(f"  [DRY RUN] would email {email}")
                sent += 1
                continue

            self._send(email, order, season, subject, highlight, campaign_name)
            sent += 1

        self.stdout.write(self.style.SUCCESS(
            f"Done. Sent: {sent}  Skipped (unsubscribed): {skipped_unsub}  "
            f"Skipped (already sent for {season!r}): {skipped_already_this_season}"
        ))

    def _send(self, email, order, season, subject, highlight, campaign_name):
        unsub_token = make_unsubscribe_token(email)
        context = {
            "name": order.full_name.split(" ")[0] if order.full_name else "there",
            "season": season,
            "subject": subject,
            "highlight": highlight,
            "shop_url": f"{settings.SITE_URL}/seeds/",
            "unsubscribe_url": f"{settings.SITE_URL}/accounts/unsubscribe/{unsub_token}/",
        }
        html_message = render_to_string("accounts/emails/seasonal_email.html", context)
        plain_message = strip_tags(html_message)

        try:
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                html_message=html_message,
                fail_silently=False,
            )
            CampaignSend.objects.update_or_create(email=email, campaign=campaign_name)
            self.stdout.write(f"  ✅ sent to {email}")
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"  ❌ failed for {email}: {e}"))
