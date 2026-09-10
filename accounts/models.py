from django.db import models


class MarketingEmailPreference(models.Model):
    """
    Tracks re-engagement/marketing email state per customer email address
    (not per User, since guest checkouts have no account).
    Lets the win-back cron avoid re-emailing too often and honors unsubscribes.
    """
    email = models.EmailField(unique=True, db_index=True)
    unsubscribed = models.BooleanField(default=False)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)
    last_campaign_sent_at = models.DateTimeField(null=True, blank=True)
    last_campaign_name = models.CharField(max_length=100, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        status = "unsubscribed" if self.unsubscribed else "subscribed"
        return f"{self.email} ({status})"
