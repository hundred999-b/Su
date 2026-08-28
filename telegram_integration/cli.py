import sys

import django

django.setup()

from .handlers import (
    start,
    help_text,
    product_list,
    product_info,
    wallet_info,
    orders_info,
)


def main():

    print("=" * 60)
    print("LOCAL TELEGRAM MARKETPLACE TEST CLIENT")
    print("=" * 60)
    print()

    telegram_id = 999999999
    username = "local_test_user"

    print(start(
        telegram_id,
        username,
    ))

    print()
    print(product_list())

    print()
    print(wallet_info(
        telegram_id,
        username,
    ))

    print()
    print(orders_info(
        telegram_id,
        username,
    ))


if __name__ == "__main__":
    main()
