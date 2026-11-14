from django.core.exceptions import ImproperlyConfigured
from decouple import config, UndefinedValueError

def _build_client():
    try:
        from phonepe.sdk.pg.payments.v2.standard_checkout_client import StandardCheckoutClient
        from phonepe.sdk.pg.env import Env

        phonepe_env = config("PHONEPE_ENV", default="SANDBOX")
        env = Env.PRODUCTION if phonepe_env == "PRODUCTION" else Env.SANDBOX

        return StandardCheckoutClient.get_instance(
            client_id=config("PHONEPE_CLIENT_ID"),
            client_secret=config("PHONEPE_CLIENT_SECRET"),
            client_version=config("PHONEPE_CLIENT_VERSION", cast=int),
            env=env,
        )
    except UndefinedValueError as e:
        raise ImproperlyConfigured(
            f"PhonePe configuration missing from .env: {e}. "
            "Set PHONEPE_CLIENT_ID, PHONEPE_CLIENT_SECRET, and PHONEPE_CLIENT_VERSION."
        ) from e
    except Exception as e:
        raise ImproperlyConfigured(
            f"Failed to initialise PhonePe SDK: {e}"
        ) from e

client = _build_client()
