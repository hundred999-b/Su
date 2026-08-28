from django.db import migrations

CURRENCIES = [
    ("USD", "US Dollar", "$", 2), ("EUR", "Euro", "€", 2), ("GBP", "Pound Sterling", "£", 2),
    ("JPY", "Japanese Yen", "¥", 0), ("CNY", "Chinese Yuan", "¥", 2), ("HKD", "Hong Kong Dollar", "HK$", 2),
    ("SGD", "Singapore Dollar", "S$", 2), ("AUD", "Australian Dollar", "A$", 2), ("NZD", "New Zealand Dollar", "NZ$", 2),
    ("CAD", "Canadian Dollar", "C$", 2), ("CHF", "Swiss Franc", "CHF", 2), ("SEK", "Swedish Krona", "kr", 2),
    ("NOK", "Norwegian Krone", "kr", 2), ("DKK", "Danish Krone", "kr", 2), ("PLN", "Polish Zloty", "zł", 2),
    ("CZK", "Czech Koruna", "Kč", 2), ("HUF", "Hungarian Forint", "Ft", 2), ("RON", "Romanian Leu", "lei", 2),
    ("TRY", "Turkish Lira", "₺", 2), ("AED", "UAE Dirham", "د.إ", 2), ("SAR", "Saudi Riyal", "﷼", 2),
    ("ZAR", "South African Rand", "R", 2), ("GHS", "Ghanaian Cedi", "GH₵", 2), ("KES", "Kenyan Shilling", "KSh", 2),
    ("NGN", "Nigerian Naira", "₦", 2), ("INR", "Indian Rupee", "₹", 2), ("BRL", "Brazilian Real", "R$", 2),
    ("MXN", "Mexican Peso", "$", 2), ("ARS", "Argentine Peso", "$", 2), ("CLP", "Chilean Peso", "$", 0),
    ("COP", "Colombian Peso", "$", 2), ("PEN", "Peruvian Sol", "S/", 2), ("THB", "Thai Baht", "฿", 2),
    ("MYR", "Malaysian Ringgit", "RM", 2), ("IDR", "Indonesian Rupiah", "Rp", 2), ("PHP", "Philippine Peso", "₱", 2),
    ("KRW", "South Korean Won", "₩", 0), ("VND", "Vietnamese Dong", "₫", 0), ("ILS", "Israeli New Shekel", "₪", 2),
]


def seed(apps, schema_editor):
    Currency = apps.get_model("finance", "SupportedCurrency")
    for code, name, symbol, decimals in CURRENCIES:
        Currency.objects.get_or_create(code=code, defaults={"name": name, "symbol": symbol, "decimal_places": decimals, "enabled": True})


def unseed(apps, schema_editor):
    Currency = apps.get_model("finance", "SupportedCurrency")
    Currency.objects.filter(code__in=[x[0] for x in CURRENCIES]).delete()


class Migration(migrations.Migration):
    dependencies = [("finance", "0004_paymentgatewayconfig")]
    operations = [migrations.RunPython(seed, unseed)]
