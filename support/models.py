from django.conf import settings
from django.db import models


class SupportSettings(models.Model):
    """
    Singleton, fully admin-controlled — nothing here is hardcoded.
    An admin can change these numbers from the dashboard at any
    time and it takes effect on the next ticket/queue check.
    """

    singleton = models.BooleanField(default=True, unique=True, editable=False)

    max_open_tickets_per_agent = models.PositiveIntegerField(
        default=7,
        help_text="An agent can't be assigned a new ticket while they already "
                   "have this many open. Adjustable per-agent below as well.",
    )

    agent_response_timeout_minutes = models.PositiveIntegerField(
        default=15,
        help_text="Once an agent claims a ticket, the requester has this long "
                   "to say something. If they go quiet, the ticket expires and "
                   "the agent is freed up for the next person.",
    )

    closing_message = models.TextField(
        default="This ticket is now being closed. Thanks for reaching out — "
                "reply anytime to open a new one if you need further help.",
    )

    expiry_message = models.TextField(
        default="We didn't hear back from you in time, so this support "
                "session has expired and you've been removed from the queue. "
                "Feel free to reach out again whenever you're ready.",
    )

    queue_notice_message = models.TextField(
        default="You've been added to the live agent queue. Heads up: once "
                "an agent is matched to you, you'll need to respond within "
                "the response window or you'll be removed from the queue "
                "and will need to request an agent again.",
    )

    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        return cls.objects.get_or_create(pk=1)[0]


class SupportField(models.Model):
    """An area of expertise, e.g. 'Payments', 'Escrow', 'Technical'."""

    name = models.CharField(max_length=80, unique=True)
    description = models.CharField(max_length=255, blank=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class SupportAgent(models.Model):
    """
    A staff member who can be assigned support tickets. Being a
    Django staff user isn't enough by itself — an admin has to
    explicitly add someone here, choose their expertise fields,
    and can optionally override the global capacity limit for
    that specific person.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="support_agent_profile",
    )
    fields = models.ManyToManyField(SupportField, blank=True, related_name="agents")
    is_available = models.BooleanField(
        default=True,
        help_text="Turn off to stop receiving new tickets without removing the agent.",
    )
    max_open_tickets_override = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Leave blank to use the global default from Support Settings.",
    )
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.username

    def effective_max_tickets(self):
        if self.max_open_tickets_override is not None:
            return self.max_open_tickets_override
        return SupportSettings.get_solo().max_open_tickets_per_agent


class KnowledgeEntry(models.Model):
    """
    A pattern → response pair the bot uses to auto-answer common
    questions. Admins add/edit these from the dashboard to
    "upgrade the bot's knowledge" without touching code.
    """

    field = models.ForeignKey(
        SupportField, on_delete=models.SET_NULL, null=True, blank=True, related_name="knowledge_entries",
    )
    trigger_keywords = models.CharField(
        max_length=500,
        help_text="Comma-separated keywords/phrases. Case-insensitive substring match "
                   "against the user's message. e.g. 'refund, money back, didn't receive'",
    )
    response = models.TextField()
    priority = models.IntegerField(
        default=0, help_text="Higher priority entries are checked first when multiple match.",
    )
    active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-priority", "id"]

    def keyword_list(self):
        return [k.strip().lower() for k in self.trigger_keywords.split(",") if k.strip()]

    def __str__(self):
        return self.trigger_keywords[:60]


class Ticket(models.Model):
    OPEN = "open"                    # bot handling / unassigned
    WAITING_AGENT = "waiting_agent"  # requester asked for a human, queued
    ASSIGNED = "assigned"            # a live agent has claimed it
    RESOLVED = "resolved"
    CLOSED = "closed"
    EXPIRED = "expired"              # requester went quiet, auto-closed

    STATUS_CHOICES = [
        (OPEN, "Open — bot handling"),
        (WAITING_AGENT, "Waiting for a live agent"),
        (ASSIGNED, "Assigned to an agent"),
        (RESOLVED, "Resolved"),
        (CLOSED, "Closed"),
        (EXPIRED, "Expired — no response"),
    ]

    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="support_tickets",
    )
    related_order = models.ForeignKey(
        'marketplace.Order', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='support_tickets',
        help_text='Optional ShopU marketplace order this ticket concerns.',
    )
    field = models.ForeignKey(
        SupportField, on_delete=models.SET_NULL, null=True, blank=True, related_name="tickets",
    )
    subject = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=OPEN)

    assigned_agent = models.ForeignKey(
        SupportAgent, on_delete=models.SET_NULL, null=True, blank=True, related_name="tickets",
    )

    requested_live_agent = models.BooleanField(default=False)
    live_agent_requested_at = models.DateTimeField(null=True, blank=True)

    claimed_at = models.DateTimeField(null=True, blank=True)
    response_deadline = models.DateTimeField(
        null=True, blank=True,
        help_text="Requester must send a message by this time or the ticket auto-expires.",
    )

    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=("status", "response_deadline")),
            models.Index(fields=("status", "created_at")),
        ]

    def __str__(self):
        return f"Ticket #{self.pk} ({self.status})"


class TicketMessage(models.Model):
    BOT = "bot"
    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"

    ROLE_CHOICES = [
        (BOT, "Bot"), (USER, "Requester"), (AGENT, "Agent"), (SYSTEM, "System"),
    ]

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
    )
    content = models.TextField(max_length=5000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
