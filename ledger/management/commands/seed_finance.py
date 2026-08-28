from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

from ledger.models import LedgerAccount
from ledger.wallet_models import Wallet


class Command(BaseCommand):
    help = "Create the basic local marketplace financial accounts"


    def handle(self, *args, **options):

        users = User.objects.all()

        currencies = ["USD"]

        for currency in currencies:

            LedgerAccount.objects.get_or_create(
                name="ESCROW",
                currency=currency,
                defaults={
                    "account_type": LedgerAccount.LIABILITY,
                },
            )

            LedgerAccount.objects.get_or_create(
                name="PLATFORM_REVENUE",
                currency=currency,
                defaults={
                    "account_type": LedgerAccount.REVENUE,
                },
            )

            LedgerAccount.objects.get_or_create(
                name="PAYMENT_CLEARING",
                currency=currency,
                defaults={
                    "account_type": LedgerAccount.ASSET,
                },
            )

            for user in users:

                account_type = LedgerAccount.LIABILITY

                account, _ = LedgerAccount.objects.get_or_create(
                    name=f"BUYER:{user.id}",
                    currency=currency,
                    defaults={
                        "account_type": account_type,
                    },
                )

                Wallet.objects.get_or_create(
                    user=user,
                    currency=currency,
                    defaults={
                        "ledger_account": account,
                    },
                )

                seller_account, _ = LedgerAccount.objects.get_or_create(
                    name=f"SELLER:{user.id}",
                    currency=currency,
                    defaults={
                        "account_type": LedgerAccount.LIABILITY,
                    },
                )

        self.stdout.write(
            self.style.SUCCESS(
                "Financial accounts initialized."
            )
        )
