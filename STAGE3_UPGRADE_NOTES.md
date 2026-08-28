# ShopU Stage 3 Upgrade

## Implemented in this build

### Marketplace listing protection
- Full-description requirement (minimum 30 characters).
- Seller condition field.
- Seller terms/return-details field.
- Mandatory seller disclosure acknowledgment.
- Mandatory seller fee/terms acknowledgment.
- Platform seller listing policy exposed through the Mini App.
- Listing versions recorded as immutable evidence.
- Policy version/content copied into listing evidence.
- Buyer disclosure acknowledgment required before purchase.
- Order stores the listing version and the description/condition/specifications/seller terms/policy content shown at purchase.
- Django Admin exposes listing policies, listing versions and order evidence.

### Financial workflow foundation
- Bank-transfer deposit creation/confirmation/failure services.
- Idempotent payment creation and payment settlement foundation.
- Crypto asset configuration checks and crypto deposit/withdrawal reservation services.
- Withdrawal reservation/completion/failure ledger flows.
- Withdrawal fee accounting corrected so ledger transactions balance when a fee is charged.
- Admin actions for bank-transfer confirmation/failure and withdrawal processing/completion/failure.

## Important testing note

The build environment used to prepare this archive does not contain Django, so Django's runtime test suite could not be executed here. Python compilation was run across the project successfully.

After extracting on the project environment, run:

```bash
python3 manage.py check
python3 manage.py makemigrations --check --dry-run
python3 manage.py migrate
python3 manage.py test
```

If `makemigrations --check --dry-run` reports changes, do not ignore them; inspect them before deployment.

## Financial integration note

The `Payment` model now has an optional user association. Existing payment-provider integrations should supply the user when creating payments before calling settlement.

Crypto payout amounts are currently represented as a USD wallet reservation until a provider/rate-conversion layer is connected. Do not treat this as an on-chain payout implementation.

## Seller/dispute evidence principle

The marketplace records what was published and what the buyer acknowledged at purchase. This is evidence for dispute handling; it does not automatically determine the outcome of a dispute. Fraud, prohibited omissions, safety issues, misrepresentation and marketplace rules still apply.
