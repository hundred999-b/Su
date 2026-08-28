from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from stage4.models import ListingRule, TermsDocument


POLICIES = [
    ("seller", "ShopU Seller Terms", """
These Seller Terms govern seller participation on ShopU.

Sellers must provide complete, accurate and truthful information about every listing.
Descriptions must disclose material defects, limitations, missing components, compatibility
information and other facts reasonably necessary for an informed purchase.

Sellers must acknowledge applicable marketplace fees and seller-specific terms before
publishing a listing.

Sellers must not publish fraudulent, misleading, counterfeit, stolen, prohibited or
unlawful goods or services.

ShopU may moderate, suspend, remove or restrict listings or accounts that violate these
requirements or applicable law.
"""),

    ("buyer", "ShopU Buyer Terms", """
These Buyer Terms govern purchases made through ShopU.

Buyers are responsible for reviewing the complete listing description, price, condition,
seller terms and applicable disclosures before purchasing.

By proceeding with a purchase, the buyer acknowledges that the displayed listing information
was available for review.

Buyers must use truthful account information and must not abuse refunds, disputes, payment
systems or marketplace protections.
"""),

    ("marketplace", "ShopU Marketplace Rules", """
These Marketplace Rules establish the general operating standards for ShopU.

Users must act honestly and must not use ShopU for fraud, deception, illegal transactions,
market manipulation, abuse, harassment or circumvention of marketplace controls.

Listings must accurately represent the goods or services being offered.

ShopU may moderate content, restrict accounts, suspend transactions or take other
appropriate action where marketplace rules are violated.
"""),

    ("escrow", "ShopU Escrow Rules", """
ShopU escrow is designed to hold transaction funds according to the applicable transaction
workflow.

Funds may be released when the applicable release conditions are satisfied, including
buyer confirmation or an applicable automatic-release rule.

Refunds and releases must be processed through the authorized escrow workflow.

Users must not attempt to bypass escrow controls or manipulate transaction status.
"""),

    ("payments", "ShopU Payments Policy", """
This policy governs payment processing on ShopU.

Users must provide accurate payment information and must not use unauthorized payment
methods, stolen payment credentials or fraudulent payment activity.

Payment status is determined by authorized payment records and transaction verification.

ShopU may delay, reject or review transactions where fraud, payment errors or compliance
concerns are detected.
"""),

    ("crypto", "ShopU Crypto Payment Policy", """
Crypto payments must be sent using the exact supported asset and network displayed for
the transaction.

Users are responsible for verifying the destination address, network and amount before
sending funds.

Blockchain transactions may be irreversible. ShopU cannot guarantee recovery of funds
sent to an incorrect address or unsupported network.

Transactions may be subject to confirmation requirements before being credited.
"""),

    ("gift_cards", "ShopU Gift Card Policy", """
Gift cards must be legitimately obtained and accurately represented.

Users must not sell counterfeit, stolen, fraudulently obtained, already-redeemed or
otherwise invalid gift cards.

Gift-card transactions may be subject to verification before funds are released.

Where permitted, disputes concerning gift cards may require evidence of validity,
ownership and redemption status.
"""),

    ("bank_transfer", "ShopU Bank Transfer Policy", """
Bank-transfer payments must use the payment instructions generated or approved by ShopU.

Users must not submit fraudulent payment confirmations, altered receipts or false
transaction references.

Bank-transfer transactions may remain pending until independently verified.

ShopU may request additional information when a transfer cannot be reliably matched to
the relevant transaction.
"""),

    ("withdrawals", "ShopU Withdrawals Policy", """
Withdrawals are subject to account eligibility, available balance and applicable
transaction controls.

Users must provide accurate withdrawal information.

ShopU may delay or review withdrawals for security, fraud prevention, transaction
verification or compliance purposes.

Users must not attempt to withdraw funds that are unavailable, disputed, held in escrow
or otherwise restricted.
"""),

    ("disputes", "ShopU Dispute & Resolution Policy", """
Disputes should be submitted through the authorized ShopU dispute process.

Users should provide truthful and relevant evidence, including listing information,
messages, transaction records, delivery evidence and other supporting material.

The marketplace may review the preserved listing version and transaction evidence when
determining a dispute.

False evidence, fabricated claims or deliberate manipulation of dispute procedures may
result in account restrictions.
"""),

    ("vendor_verification", "ShopU Vendor Verification Policy", """
Certain sellers may be required to complete vendor verification before accessing
particular marketplace functions.

Information submitted for verification must be accurate and truthful.

Approval does not guarantee acceptance of every listing or transaction.

ShopU may reject, suspend or re-review verification where information is incomplete,
inaccurate or raises legitimate security or compliance concerns.
"""),

    ("prohibited_items", "ShopU Prohibited Items Policy", """
Users must not list, sell, purchase or facilitate transactions involving prohibited
goods or services.

Prohibited categories include unlawful goods, stolen property, counterfeit goods,
fraudulent credentials, malicious services and other items restricted by applicable
law or ShopU policy.

ShopU may remove prohibited listings and restrict accounts associated with prohibited
activity.
"""),

    ("privacy", "ShopU Privacy Policy", """
ShopU may process information necessary to operate accounts, listings, transactions,
payments, escrow, disputes, security and customer support.

Information may include account information, transaction records, listing evidence,
security information and communications relevant to marketplace operations.

ShopU should retain information only as reasonably necessary for legitimate operational,
security, legal or dispute-resolution purposes and apply appropriate safeguards.
"""),

    ("account_security", "ShopU Account Security Policy", """
Users are responsible for protecting their account credentials and authorized access.

Users must not share passwords, authentication credentials or recovery information in
an unsafe manner.

Users must promptly report suspected unauthorized access or account compromise.

ShopU may apply security restrictions or additional verification when suspicious activity
is detected.
"""),

    ("refunds", "ShopU Refund & Cancellation Policy", """
Refunds and cancellations are governed by the applicable transaction state, listing
terms, payment method and dispute process.

Transactions already released from escrow may require additional review before any
refund can be considered.

Refund decisions should rely on preserved transaction and listing evidence.

Users must not abuse cancellation or refund mechanisms through fraudulent claims.
"""),
]


class Command(BaseCommand):
    help = "Create the initial ShopU Stage 4 rules and policy documents."

    def handle(self, *args, **kwargs):
        ListingRule.get_solo()

        User = get_user_model()
        admin = User.objects.filter(is_superuser=True).first()

        if not admin:
            self.stdout.write(
                self.style.WARNING(
                    "No superuser exists; create one before publishing terms."
                )
            )
            return

        created = 0
        existing = 0

        for kind, title, body in POLICIES:
            obj, was_created = TermsDocument.objects.get_or_create(
                kind=kind,
                version="1.0",
                defaults={
                    "title": title,
                    "body": body.strip(),
                    "active": False,
                    "created_by": admin,
                },
            )

            if was_created:
                created += 1
            else:
                existing += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Stage 4 policy configuration complete. "
                f"Created: {created}; Existing: {existing}; Total policy types: {len(POLICIES)}."
            )
        )
