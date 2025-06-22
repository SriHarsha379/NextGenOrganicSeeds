from phonepe.sdk.pg.payments.v2.standard_checkout_client import StandardCheckoutClient
from phonepe.sdk.pg.env import Env
from decouple import config

env = Env.PRODUCTION if config("PHONEPE_ENV") == "PRODUCTION" else Env.SANDBOX

client = StandardCheckoutClient.get_instance(
    client_id=config("PHONEPE_CLIENT_ID"),
    client_secret=config("PHONEPE_CLIENT_SECRET"),
    client_version=config("PHONEPE_CLIENT_VERSION", cast=int),
    env=env
)
