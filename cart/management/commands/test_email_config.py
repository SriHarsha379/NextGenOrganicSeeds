from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings


class Command(BaseCommand):
    help = "Test email configuration by sending a test email"

    def add_arguments(self, parser):
        parser.add_argument(
            '--to',
            type=str,
            default=None,
            help='Recipient email address (defaults to ADMIN_NOTIFICATION_EMAIL)',
        )

    def handle(self, *args, **kwargs):
        recipient = kwargs['to'] or getattr(settings, 'ADMIN_NOTIFICATION_EMAIL', settings.EMAIL_HOST_USER)

        self.stdout.write("📧 Email Configuration:")
        self.stdout.write(f"   EMAIL_BACKEND  : {settings.EMAIL_BACKEND}")
        self.stdout.write(f"   EMAIL_HOST     : {settings.EMAIL_HOST}")
        self.stdout.write(f"   EMAIL_PORT     : {settings.EMAIL_PORT}")
        self.stdout.write(f"   EMAIL_USE_TLS  : {settings.EMAIL_USE_TLS}")
        self.stdout.write(f"   EMAIL_USE_SSL  : {settings.EMAIL_USE_SSL}")
        self.stdout.write(f"   EMAIL_HOST_USER: {settings.EMAIL_HOST_USER}")
        self.stdout.write(f"   EMAIL_PASSWORD : {'[SET]' if settings.EMAIL_HOST_PASSWORD else '[NOT SET]'}")
        self.stdout.write(f"   FROM           : {settings.DEFAULT_FROM_EMAIL}")
        self.stdout.write(f"   TO             : {recipient}")
        self.stdout.write("")

        try:
            send_mail(
                subject="✅ Hasa Farm — Email Configuration Test",
                message=(
                    "This is a test email from Hasa Farm.\n\n"
                    "If you received this, your email configuration is working correctly.\n\n"
                    "Regards,\nHasa Organic Seeds"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient],
                fail_silently=False,
            )
            self.stdout.write(self.style.SUCCESS(f"✅ Test email sent successfully to {recipient}"))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"❌ Failed to send test email: {e}"))
            raise SystemExit(1)
