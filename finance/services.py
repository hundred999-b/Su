from decimal import Decimal
from .models import CommissionRule

def calculate_fee(fee_type, amount, currency="USD"):
    amount = Decimal(str(amount))
    rules = CommissionRule.objects.filter(
        fee_type=fee_type, currency=currency, enabled=True
    )
    percentage = sum((r.percentage for r in rules), Decimal("0"))
    fixed = sum((r.fixed_amount for r in rules), Decimal("0"))
    return (amount * percentage / Decimal("100") + fixed).quantize(Decimal("0.01"))
