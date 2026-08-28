from django.contrib import admin, messages

from adminpanel.admin_mixins import ShopUModelAdmin, _allowed

from .models import (
    KnowledgeEntry,
    SupportAgent,
    SupportField,
    SupportSettings,
    Ticket,
    TicketMessage,
)
from .services import claim_ticket_manually, escalate_to_field, resolve_ticket


@admin.register(SupportSettings)
class SupportSettingsAdmin(ShopUModelAdmin):
    list_display = (
        "max_open_tickets_per_agent",
        "agent_response_timeout_minutes",
        "updated_at",
    )

    def has_add_permission(self, request):
        if not _allowed(request, self.model, "add"):
            return False
        return not SupportSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SupportField)
class SupportFieldAdmin(ShopUModelAdmin):
    list_display = ("name", "active")
    search_fields = ("name",)


@admin.register(SupportAgent)
class SupportAgentAdmin(ShopUModelAdmin):
    list_display = (
        "user",
        "is_available",
        "active",
        "effective_max_tickets",
        "open_ticket_count",
    )
    list_filter = ("is_available", "active", "fields")
    filter_horizontal = ("fields",)
    search_fields = ("user__username",)

    def open_ticket_count(self, obj):
        return obj.tickets.filter(status=Ticket.ASSIGNED).count()

    open_ticket_count.short_description = "Open now"


@admin.register(KnowledgeEntry)
class KnowledgeEntryAdmin(ShopUModelAdmin):
    list_display = (
        "trigger_keywords",
        "field",
        "priority",
        "active",
        "created_by",
        "updated_at",
    )
    list_filter = ("active", "field")
    search_fields = ("trigger_keywords", "response")

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


class TicketMessageInline(admin.TabularInline):
    model = TicketMessage
    extra = 0
    readonly_fields = ("role", "sender", "content", "created_at")
    can_delete = False


@admin.register(Ticket)
class TicketAdmin(ShopUModelAdmin):
    list_display = (
        "id",
        "requester",
        "related_order",
        "field",
        "status",
        "assigned_agent",
        "created_at",
        "response_deadline",
    )
    list_filter = ("status", "field", "requested_live_agent")
    search_fields = (
        "requester__username",
        "subject",
        "related_order__id",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
        "claimed_at",
        "resolved_at",
        "closed_at",
    )
    inlines = [TicketMessageInline]
    actions = ["action_claim", "action_resolve"]

    @admin.action(description="Claim selected waiting tickets (as me)")
    def action_claim(self, request, queryset):
        if not request.user.is_superuser and not _allowed(
            request, Ticket, "change"
        ):
            self.message_user(
                request,
                "You do not have permission to claim support tickets.",
                level=messages.ERROR,
            )
            return

        count = 0

        for ticket in queryset:
            try:
                claim_ticket_manually(request.user, ticket.pk)
                count += 1
            except Exception as exc:
                self.message_user(
                    request,
                    f"Ticket #{ticket.pk}: {exc}",
                    level=messages.ERROR,
                )

        if count:
            self.message_user(
                request,
                f"Claimed {count} ticket(s).",
                level=messages.SUCCESS,
            )

    @admin.action(description="Resolve selected tickets (assigned to me)")
    def action_resolve(self, request, queryset):
        if not request.user.is_superuser and not _allowed(
            request, Ticket, "change"
        ):
            self.message_user(
                request,
                "You do not have permission to resolve support tickets.",
                level=messages.ERROR,
            )
            return

        count = 0

        for ticket in queryset:
            try:
                resolve_ticket(request.user, ticket.pk)
                count += 1
            except Exception as exc:
                self.message_user(
                    request,
                    f"Ticket #{ticket.pk}: {exc}",
                    level=messages.ERROR,
                )

        if count:
            self.message_user(
                request,
                f"Resolved {count} ticket(s).",
                level=messages.SUCCESS,
            )


@admin.register(TicketMessage)
class TicketMessageAdmin(ShopUModelAdmin):
    list_display = ("id", "ticket", "role", "sender", "created_at")
    list_filter = ("role",)
    search_fields = (
        "ticket__id",
        "ticket__requester__username",
        "content",
    )
    readonly_fields = ("created_at",)
