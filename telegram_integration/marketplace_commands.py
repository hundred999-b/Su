from decimal import Decimal, InvalidOperation

from django.db import transaction

from ledger.transaction_service import (
    test_deposit,
    wallet_balance,
    purchase_order,
)

from marketplace.models import Product, Order
from marketplace.services import purchase_product

from .bot import get_or_create_telegram_user


def command_products():
    products = Product.objects.filter(
        active=True
    ).order_by("id")

    if not products.exists():
        return "No products available."

    lines = ["🛍 AVAILABLE PRODUCTS", ""]

    for product in products:
        lines.append(
            f"#{product.id} "
            f"{product.title} — "
            f"{product.price} {product.currency}"
        )

    lines.append("")
    lines.append("Use /product <id> to view details.")

    return "\n".join(lines)


def command_product(product_id):
    try:
        product_id = int(product_id)
    except (TypeError, ValueError):
        return "Usage: /product <id>"

    product = Product.objects.filter(
        pk=product_id,
        active=True,
    ).select_related("seller").first()

    if not product:
        return "Product not found."

    return (
        f"🛍 {product.title}\n\n"
        f"{product.description}\n\n"
        f"Price: {product.price} {product.currency}\n"
        f"Seller: {product.seller.username}\n"
        f"Product ID: {product.id}\n\n"
        f"To purchase: /buy {product.id}"
    )


def command_wallet(telegram_id, username=None):
    user = get_or_create_telegram_user(
        telegram_id,
        username,
    )

    balance = wallet_balance(user, "USD")

    return (
        "💰 WALLET\n\n"
        f"Balance: {balance} USD"
    )


def command_testdeposit(
    telegram_id,
    username=None,
    amount="100",
):
    user = get_or_create_telegram_user(
        telegram_id,
        username,
    )

    try:
        amount = Decimal(str(amount))
    except InvalidOperation:
        return "Invalid amount."

    if amount <= 0:
        return "Amount must be greater than zero."

    # Explicit development-only guard.
    from django.conf import settings

    if not getattr(settings, "DEBUG", False):
        return "Test deposits are disabled."

    tx = test_deposit(
        user,
        amount,
        "USD",
    )

    return (
        "🧪 TEST DEPOSIT COMPLETE\n\n"
        f"Amount: {amount} USD\n"
        f"Transaction: {tx.transaction_id}\n"
        f"New balance: {wallet_balance(user, 'USD')} USD"
    )


def command_accept_terms(telegram_id, username=None):
    from stage4.models import TermsDocument
    from stage4.services import active_terms, accept_terms

    user = get_or_create_telegram_user(telegram_id, username)
    terms = active_terms(TermsDocument.BUYER)
    if not terms:
        return "Buyer Terms are not configured."
    acceptance = accept_terms(user, terms, purpose="purchase")
    return f"Buyer Terms {terms.version} accepted at {acceptance.accepted_at.isoformat()}."


def command_buy(telegram_id, product_id, username=None):
    user = get_or_create_telegram_user(telegram_id, username)
    try:
        product_id = int(product_id)
    except (TypeError, ValueError):
        return "Usage: /buy <product_id>"

    try:
        order, tx = purchase_product(
            buyer=user,
            product_id=product_id,
            disclosure_acknowledged=True,
        )
    except PermissionError:
        return "Please accept the current Buyer Terms first with /acceptterms."
    except ValueError as e:
        return f"❌ {e}"

    return (
        "✅ PURCHASE CREATED\n\n"
        f"Order: #{order.id}\n"
        f"Product: {order.product_title_snapshot}\n"
        f"Amount: {order.amount} {order.currency}\n"
        "Escrow: FUNDED\n"
        f"Transaction: {tx.transaction_id}\n\n"
        f"Remaining balance: "
        f"{wallet_balance(user, order.currency)} {order.currency}"
    )


def command_orders(
    telegram_id,
    username=None,
):
    user = get_or_create_telegram_user(
        telegram_id,
        username,
    )

    orders = (
        Order.objects
        .filter(buyer=user)
        .select_related("product")
        .order_by("-id")
    )

    if not orders.exists():
        return "📦 You have no orders."

    lines = ["📦 YOUR ORDERS", ""]

    for order in orders:
        lines.append(
            f"#{order.id} "
            f"{order.product.title} — "
            f"{order.amount} {order.currency} — "
            f"{order.status}"
        )

    return "\n".join(lines)


def command_order(
    telegram_id,
    order_id,
    username=None,
):
    user = get_or_create_telegram_user(
        telegram_id,
        username,
    )

    try:
        order_id = int(order_id)
    except (TypeError, ValueError):
        return "Usage: /order <id>"

    order = (
        Order.objects
        .filter(
            pk=order_id,
            buyer=user,
        )
        .select_related("product")
        .first()
    )

    if not order:
        return "Order not found."

    return (
        f"📦 ORDER #{order.id}\n\n"
        f"Product: {order.product.title}\n"
        f"Amount: {order.amount} {order.currency}\n"
        f"Status: {order.status}"
    )
