from .bot import (
    get_or_create_telegram_user,
    products,
    product_details,
    user_orders,
    user_wallet,
)


def start(
    telegram_user_id,
    username=None,
):
    user = get_or_create_telegram_user(
        telegram_user_id,
        username,
    )

    return (
        f"Welcome to the marketplace, "
        f"{user.username}.\n\n"
        "Commands:\n"
        "/products - browse products\n"
        "/wallet - view wallet\n"
        "/orders - view orders\n"
        "/help - show help"
    )


def help_text():
    return (
        "Marketplace commands:\n\n"
        "/products\n"
        "/wallet\n"
        "/orders\n"
        "/help"
    )


def product_list():
    items = products()

    if not items:
        return "No products are currently available."

    lines = ["AVAILABLE PRODUCTS", ""]

    for product in items:
        lines.append(
            f"#{product.id} "
            f"{product.title} — "
            f"{product.price} {product.currency}"
        )

    lines.append("")
    lines.append(
        "Use /product ID to view a product."
    )

    return "\n".join(lines)


def product_info(product_id):
    product = product_details(product_id)

    if not product:
        return "Product not found."

    return (
        f"{product.title}\n\n"
        f"{product.description}\n\n"
        f"Price: {product.price} {product.currency}\n"
        f"Seller: {product.seller.username}\n\n"
        f"ID: {product.id}"
    )


def wallet_info(
    telegram_user_id,
    username=None,
):
    user = get_or_create_telegram_user(
        telegram_user_id,
        username,
    )

    balance = user_wallet(user)

    return (
        f"Wallet\n\n"
        f"Currency: USD\n"
        f"Balance: {balance}"
    )


def orders_info(
    telegram_user_id,
    username=None,
):
    user = get_or_create_telegram_user(
        telegram_user_id,
        username,
    )

    orders = user_orders(user)

    if not orders:
        return "You have no orders."

    lines = ["YOUR ORDERS", ""]

    for order in orders:
        lines.append(
            f"#{order.id} "
            f"{order.product.title} — "
            f"{order.amount} {order.currency} — "
            f"{order.status}"
        )

    return "\n".join(lines)
