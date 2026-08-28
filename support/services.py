"""
Support ticket engine.

Rules encoded here (per spec):
  - Capacity per agent is admin-configurable, never hardcoded.
  - An agent at their open-ticket limit cannot be assigned another
    until one of their current tickets is resolved/closed/expired.
  - Bot answers first from admin-curated knowledge entries; if it
    can't help (or the requester asks for a human), it escalates.
  - Once a live agent is matched, the requester has a configurable
    window to respond or the ticket auto-expires and the agent is
    freed for the next person in the queue.
  - A closing message always goes out before a ticket is actually
    closed — whether it was resolved or expired.
"""

from django.db import transaction
from django.utils import timezone

from audit.models import AuditEvent
from stage4.telegram import notify

from .models import KnowledgeEntry, SupportAgent, SupportSettings, Ticket, TicketMessage


def get_settings():
    return SupportSettings.get_solo()


def _log(actor, action, ticket, metadata=None):
    AuditEvent.objects.create(
        actor=actor,
        action=action,
        object_type="Ticket",
        object_id=str(ticket.pk),
        metadata=metadata or {},
    )


def _clean_message(content):
    content = str(content or '').strip()
    if not content:
        raise ValueError("Message cannot be empty.")
    if len(content) > 5000:
        raise ValueError("Message is too long (maximum 5000 characters).")
    return content

def _add_message(ticket, role, content, sender=None):
    return TicketMessage.objects.create(
        ticket=ticket, role=role, content=_clean_message(content), sender=sender
    )


# ----------------------------------------------------------------
# Bot first line
# ----------------------------------------------------------------

def match_knowledge(message_text):
    """
    Naive but effective keyword matching against admin-curated
    entries. Highest-priority match wins; first match by priority
    order if there's a tie.
    """

    text = (message_text or "").lower()

    for entry in KnowledgeEntry.objects.filter(active=True):
        for keyword in entry.keyword_list():
            if keyword and keyword in text:
                return entry

    return None


@transaction.atomic
def create_ticket(user, message, subject="", field=None, related_order=None):
    message = _clean_message(message)
    subject = str(subject or '').strip()[:200]
    if related_order is not None and related_order.buyer_id != user.id and related_order.product.seller_id != user.id:
        raise ValueError("You can only link a support ticket to an order you are involved in.")
    ticket = Ticket.objects.create(requester=user, subject=subject, field=field, related_order=related_order, status=Ticket.OPEN)
    _add_message(ticket, TicketMessage.USER, message, sender=user)

    entry = match_knowledge(message)
    if entry:
        _add_message(ticket, TicketMessage.BOT, entry.response)
        if entry.field and not ticket.field:
            ticket.field = entry.field
            ticket.save(update_fields=["field", "updated_at"])

    _log(user, "support.ticket_created", ticket, {"auto_answered": bool(entry)})

    return ticket


@transaction.atomic
def add_user_message(ticket_id, user, content):
    ticket = Ticket.objects.select_for_update().get(pk=ticket_id)

    if ticket.requester_id != user.id:
        raise ValueError("This isn't your ticket")

    if ticket.status in (Ticket.CLOSED, Ticket.EXPIRED, Ticket.RESOLVED):
        raise ValueError("This ticket is already closed")

    content = _clean_message(content)
    _add_message(ticket, TicketMessage.USER, content, sender=user)

    # Answering keeps a claimed ticket alive — push the deadline out
    # again so a genuinely active conversation never gets cut off.
    if ticket.status == Ticket.ASSIGNED and ticket.response_deadline:
        minutes = get_settings().agent_response_timeout_minutes
        ticket.response_deadline = timezone.now() + timezone.timedelta(minutes=minutes)
        ticket.save(update_fields=["response_deadline", "updated_at"])
        return ticket

    if ticket.status == Ticket.OPEN:
        entry = match_knowledge(content)
        if entry:
            _add_message(ticket, TicketMessage.BOT, entry.response)

    return ticket


@transaction.atomic
def add_agent_message(agent_user, ticket_id, content):
    content = _clean_message(content)
    agent = SupportAgent.objects.select_for_update().get(user=agent_user, active=True)
    ticket = (
        Ticket.objects.select_for_update()
        .select_related('requester')
        .get(pk=ticket_id, assigned_agent=agent)
    )
    if ticket.status != Ticket.ASSIGNED:
        raise ValueError(f"Ticket isn't currently assigned (status: {ticket.status})")
    _add_message(ticket, TicketMessage.AGENT, content, sender=agent_user)
    minutes = get_settings().agent_response_timeout_minutes
    ticket.response_deadline = timezone.now() + timezone.timedelta(minutes=minutes)
    ticket.save(update_fields=['response_deadline', 'updated_at'])
    notify(ticket.requester, 'support.agent_message', 'Support replied', content[:240])
    _log(agent_user, 'support.agent_message', ticket)
    return ticket


# ----------------------------------------------------------------
# Escalation to a live agent
# ----------------------------------------------------------------

@transaction.atomic
def request_live_agent(ticket_id, user, field=None):
    ticket = Ticket.objects.select_for_update().get(pk=ticket_id)

    if ticket.requester_id != user.id:
        raise ValueError("This isn't your ticket")

    if ticket.status in (Ticket.CLOSED, Ticket.EXPIRED, Ticket.RESOLVED):
        raise ValueError("This ticket is already closed")

    ticket.requested_live_agent = True
    ticket.live_agent_requested_at = timezone.now()
    ticket.status = Ticket.WAITING_AGENT
    if field:
        ticket.field = field
    ticket.save(update_fields=["requested_live_agent", "live_agent_requested_at", "status", "field", "updated_at"])

    _add_message(ticket, TicketMessage.SYSTEM, get_settings().queue_notice_message)
    _log(user, "support.live_agent_requested", ticket, {"field": field.name if field else None})

    try_match_queue()

    ticket.refresh_from_db()
    return ticket


def _current_load(agent):
    return Ticket.objects.filter(assigned_agent=agent, status=Ticket.ASSIGNED).count()


def _available_agent_for(field):
    """
    Least-loaded available agent under their capacity, matching the
    ticket's field when one is set. Falls back to any available
    under-capacity agent if no field is set or no field specialist
    is free — better to route to a generalist than leave someone
    waiting indefinitely.
    """

    candidates = SupportAgent.objects.filter(active=True, is_available=True)

    if field:
        field_candidates = candidates.filter(fields=field)
        pool = list(field_candidates) or list(candidates)
    else:
        pool = list(candidates)

    pool = [a for a in pool if _current_load(a) < a.effective_max_tickets()]

    if not pool:
        return None

    pool.sort(key=_current_load)
    return pool[0]


@transaction.atomic
def claim_ticket_for_queue(ticket, agent):
    """Internal: assign an agent while re-checking capacity under row lock."""
    agent = SupportAgent.objects.select_for_update().get(pk=agent.pk)
    if not agent.active or not agent.is_available:
        raise ValueError('Agent is not available.')
    current_load = Ticket.objects.filter(assigned_agent=agent, status=Ticket.ASSIGNED).count()
    if current_load >= agent.effective_max_tickets():
        raise ValueError('Agent is at capacity.')

    minutes = get_settings().agent_response_timeout_minutes
    now = timezone.now()

    ticket.assigned_agent = agent
    ticket.requested_live_agent = False
    ticket.status = Ticket.ASSIGNED
    ticket.claimed_at = now
    ticket.response_deadline = now + timezone.timedelta(minutes=minutes)
    ticket.save(update_fields=["assigned_agent", "requested_live_agent", "status", "claimed_at", "response_deadline", "updated_at"])

    _add_message(
        ticket, TicketMessage.SYSTEM,
        f"An agent is ready for you. Please respond within {minutes} minutes or "
        f"you'll be removed from the queue and will need to request an agent again.",
    )

    notify(
        agent.user, "support.ticket_assigned", "New support ticket assigned",
        f"Ticket #{ticket.pk} has been assigned to you.",
    )
    notify(
        ticket.requester, "support.agent_ready", "An agent is ready for you",
        f"Please respond in this ticket within {minutes} minutes.",
    )

    _log(None, "support.ticket_claimed", ticket, {"agent": agent.user.username})


def try_match_queue():
    """
    Walk the waiting queue oldest-first and match anyone we can to
    a free, under-capacity agent. Call this after any event that
    might free up capacity (claim, resolve, close, expire) or on a
    schedule from the maintenance job.
    """

    waiting = Ticket.objects.filter(status=Ticket.WAITING_AGENT).order_by("live_agent_requested_at")

    matched = []
    for ticket in waiting:
        agent = _available_agent_for(ticket.field)
        if agent:
            with transaction.atomic():
                locked = Ticket.objects.select_for_update().get(pk=ticket.pk)
                if locked.status != Ticket.WAITING_AGENT:
                    continue
                try:
                    claim_ticket_for_queue(locked, agent)
                except ValueError:
                    # Capacity/availability may have changed after the
                    # candidate scan. Leave the ticket queued and continue.
                    continue
                matched.append(ticket.pk)

    return matched


@transaction.atomic
def claim_ticket_manually(agent_user, ticket_id):
    """An agent explicitly picks up a waiting ticket from their dashboard."""

    agent = SupportAgent.objects.get(user=agent_user, active=True)
    ticket = Ticket.objects.select_for_update().get(pk=ticket_id)

    if ticket.status != Ticket.WAITING_AGENT:
        raise ValueError(f"Ticket is not waiting for an agent (status: {ticket.status})")

    if _current_load(agent) >= agent.effective_max_tickets():
        raise ValueError(
            f"You're at your open-ticket limit ({agent.effective_max_tickets()}). "
            "Resolve or close a ticket before taking another."
        )

    claim_ticket_for_queue(ticket, agent)
    ticket.refresh_from_db()
    return ticket


# ----------------------------------------------------------------
# Escalating between agents (specialist routing)
# ----------------------------------------------------------------

@transaction.atomic
def escalate_to_field(agent_user, ticket_id, target_field, note=""):
    """
    An agent who can't solve it forwards to a specialist. Frees the
    current agent's capacity immediately and re-enters the queue
    for automatic matching to an available expert in that field.
    """

    agent = SupportAgent.objects.get(user=agent_user)
    ticket = Ticket.objects.select_for_update().get(pk=ticket_id, assigned_agent=agent)

    ticket.assigned_agent = None
    ticket.status = Ticket.WAITING_AGENT
    ticket.field = target_field
    ticket.claimed_at = None
    ticket.response_deadline = None
    ticket.save(update_fields=["assigned_agent", "status", "field", "claimed_at", "response_deadline", "updated_at"])

    if note:
        _add_message(ticket, TicketMessage.SYSTEM, f"Forwarded to a {target_field.name} specialist.")

    _log(agent_user, "support.escalated", ticket, {"to_field": target_field.name, "note": note})

    try_match_queue()

    ticket.refresh_from_db()
    return ticket


# ----------------------------------------------------------------
# Resolving / closing
# ----------------------------------------------------------------

@transaction.atomic
def resolve_ticket(agent_user, ticket_id):
    agent = SupportAgent.objects.get(user=agent_user)
    ticket = Ticket.objects.select_for_update().get(pk=ticket_id, assigned_agent=agent)

    if ticket.status != Ticket.ASSIGNED:
        raise ValueError(f"Ticket isn't currently assigned (status: {ticket.status})")

    closing_message = get_settings().closing_message
    _add_message(ticket, TicketMessage.SYSTEM, closing_message)

    now = timezone.now()
    ticket.status = Ticket.RESOLVED
    ticket.resolved_at = now
    ticket.closed_at = None
    ticket.response_deadline = None
    ticket.save(update_fields=["status", "resolved_at", "closed_at", "response_deadline", "updated_at"])

    notify(ticket.requester, "support.ticket_closed", "Support ticket resolved", closing_message)

    _log(agent_user, "support.resolved", ticket)

    try_match_queue()

    return ticket


@transaction.atomic
def close_ticket_by_user(user, ticket_id):
    ticket = Ticket.objects.select_for_update().get(pk=ticket_id, requester=user)
    if ticket.status in (Ticket.CLOSED, Ticket.EXPIRED):
        raise ValueError('Ticket is already closed.')
    closing_message = get_settings().closing_message
    _add_message(ticket, TicketMessage.SYSTEM, closing_message)
    now = timezone.now()
    ticket.status = Ticket.CLOSED
    ticket.closed_at = now
    ticket.response_deadline = None
    ticket.requested_live_agent = False
    ticket.save(update_fields=['status','closed_at','response_deadline','requested_live_agent','updated_at'])
    notify(ticket.requester, 'support.ticket_closed', 'Support ticket closed', closing_message)
    _log(user, 'support.closed_by_user', ticket)
    try_match_queue()
    return ticket


# ----------------------------------------------------------------
# Auto-expiry (run by the maintenance job on a schedule)
# ----------------------------------------------------------------

def expire_unattended_tickets():
    """
    Any ASSIGNED ticket whose response_deadline has passed with no
    reply gets closed out: closing/expiry message sent, agent
    freed, requester informed they've been dropped from the queue.
    """

    now = timezone.now()
    due = Ticket.objects.filter(status=Ticket.ASSIGNED, response_deadline__lte=now)

    expired = []
    for ticket in due:
        with transaction.atomic():
            locked = Ticket.objects.select_for_update().get(pk=ticket.pk)
            if locked.status != Ticket.ASSIGNED or not locked.response_deadline or locked.response_deadline > now:
                continue

            message = get_settings().expiry_message
            _add_message(locked, TicketMessage.SYSTEM, message)

            locked.status = Ticket.EXPIRED
            locked.requested_live_agent = False
            locked.closed_at = now
            locked.response_deadline = None
            locked.save(update_fields=["status", "requested_live_agent", "closed_at", "response_deadline", "updated_at"])

            notify(locked.requester, "support.ticket_expired", "Support session expired", message)

            _log(None, "support.expired", locked)
            expired.append(locked.pk)

    if expired:
        try_match_queue()

    return expired


def run_support_maintenance():
    """Single entry point for the periodic cron job."""
    expired = expire_unattended_tickets()
    matched = try_match_queue()
    return {"expired": expired, "matched": matched}
