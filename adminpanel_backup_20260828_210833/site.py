from decimal import Decimal

from django.contrib import admin
from django.db.models import Sum
from django.urls import reverse
from django.utils import timezone


class ShopUAdminSite(admin.AdminSite):
    site_header = "ShopU Administration"
    site_title = "ShopU Admin"
    index_title = "Marketplace Control Center"
    index_template = "admin/index.html"

    def each_context(self, request):
        context = super().each_context(request)
        from audit.models import AuditEvent
        from adminpanel.models import StaffRole
        from escrow.models import Escrow
        from finance.models import FinanceSettings, PaymentGatewayConfig, SupportedCurrency
        from giftcards.models import GiftCardTopUp
        from marketplace.models import Order, Product
        from payments.models import Payment
        from referrals.models import ReferralProfile, ReferralProgramSettings, ReferralReward
        from stage4.models import DisputeEvent, TermsDocument
        from vendor_verification.models import VendorVerification
        from withdrawals.models import WithdrawalRequest

        def count(model, **filters):
            return model.objects.filter(**filters).count()

        def url_for(model, action="changelist"):
            try:
                return reverse(f"admin:{model._meta.app_label}_{model._meta.model_name}_{action}")
            except Exception:
                return "#"

        active_terms = TermsDocument.objects.filter(active=True).count()
        context["shopu_dashboard"] = {
            "products": count(Product, active=True),
            "orders": count(Order),
            "pending_orders": count(Order, status=Order.PENDING),
            "holding_escrow": count(Escrow, status=Escrow.HOLDING),
            "disputes": count(Order, status=Order.DISPUTED),
            "pending_payments": count(Payment, status=Payment.PENDING),
            "pending_withdrawals": count(WithdrawalRequest, status=WithdrawalRequest.PENDING),
            "pending_verification": count(VendorVerification, status=VendorVerification.PENDING),
            "referrals": count(ReferralProfile),
            "referral_rewards": count(ReferralReward),
            "active_terms": active_terms,
            "audit_events": count(AuditEvent),
            "staff_roles": count(StaffRole, active=True),
            "gift_card_topups": count(GiftCardTopUp, status=GiftCardTopUp.PENDING),
            "urls": {
                "products": url_for(Product),
                "orders": url_for(Order),
                "escrow": url_for(Escrow),
                "disputes": url_for(DisputeEvent),
                "payments": url_for(Payment),
                "withdrawals": url_for(WithdrawalRequest),
                "verification": url_for(VendorVerification),
                "referrals": url_for(ReferralProfile),
                "referral_settings": url_for(ReferralProgramSettings),
                "terms": url_for(TermsDocument),
                "audit": url_for(AuditEvent),
                "staff_roles": url_for(StaffRole),
                "finance": url_for(FinanceSettings),
                "gateways": url_for(PaymentGatewayConfig),
                "currencies": url_for(SupportedCurrency),
                "gift_cards": url_for(GiftCardTopUp),
            },
        }
        context["dashboard_cards"] = [("Active listings", "products"), ("Orders", "orders"), ("Holding escrow", "holding_escrow"), ("Disputes", "disputes"), ("Pending payments", "pending_payments"), ("Pending withdrawals", "pending_withdrawals"), ("Pending verification", "pending_verification"), ("Referral profiles", "referrals"), ("Referral rewards", "referral_rewards"), ("Pending gift-card top-ups", "gift_card_topups"), ("Active policies", "active_terms")]
        context["shopu_now"] = timezone.now()
        return context
