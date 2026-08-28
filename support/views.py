from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Prefetch

from accounts.models import Profile
from marketplace.models import Order
from telegram_integration.shopu_auth import authenticate_init_data

from .models import SupportAgent, SupportField, Ticket, TicketMessage
from .services import (
    add_agent_message, add_user_message, claim_ticket_manually, create_ticket,
    escalate_to_field, request_live_agent, resolve_ticket, close_ticket_by_user,
)

User = get_user_model()

def _user(request):
    return authenticate_init_data(request.POST.get('init_data') or request.GET.get('init_data'))

def _message_json(m):
    return {'id': m.id, 'role': m.role, 'sender_id': m.sender_id, 'content': m.content, 'created_at': m.created_at.isoformat()}

def _ticket_json(ticket, include_messages=True):
    return {
        'id': ticket.id, 'subject': ticket.subject, 'status': ticket.status,
        'field': ticket.field.name if ticket.field else None,
        'assigned_agent': ticket.assigned_agent.user.username if ticket.assigned_agent else None,
        'requested_live_agent': ticket.requested_live_agent,
        'response_deadline': ticket.response_deadline.isoformat() if ticket.response_deadline else None,
        'related_order_id': ticket.related_order_id,
        'created_at': ticket.created_at.isoformat(), 'updated_at': ticket.updated_at.isoformat(),
        'messages': [_message_json(m) for m in ticket.messages.all()] if include_messages else [],
    }

@csrf_exempt
def tickets(request):
    user = _user(request)
    if not user: return JsonResponse({'error': 'Telegram authentication required'}, status=401)
    qs = Ticket.objects.filter(requester=user).select_related('field', 'assigned_agent__user', 'related_order').prefetch_related('messages')
    return JsonResponse({'tickets': [_ticket_json(t) for t in qs.order_by('-updated_at')[:50]]})

@csrf_exempt
def create_ticket_api(request):
    if request.method != 'POST': return JsonResponse({'error': 'POST required'}, status=405)
    user = _user(request)
    if not user: return JsonResponse({'error': 'Telegram authentication required'}, status=401)
    try:
        order = None
        order_id = request.POST.get('related_order_id')
        if order_id:
            order = Order.objects.filter(pk=order_id).select_related('product').first()
            if not order: raise ValueError('Related order not found.')
        field = None
        field_id = request.POST.get('field_id')
        if field_id:
            field = SupportField.objects.filter(pk=field_id, active=True).first()
            if not field: raise ValueError('Support field not found.')
        ticket = create_ticket(user, request.POST.get('message'), request.POST.get('subject', ''), field, order)
        return JsonResponse({'ticket': _ticket_json(ticket) }, status=201)
    except Exception as exc: return JsonResponse({'error': str(exc)}, status=400)

@csrf_exempt
def ticket_detail(request, ticket_id):
    user = _user(request)
    if not user: return JsonResponse({'error': 'Telegram authentication required'}, status=401)
    ticket = Ticket.objects.filter(pk=ticket_id, requester=user).select_related('field','assigned_agent__user','related_order').prefetch_related('messages').first()
    if not ticket: return JsonResponse({'error': 'Ticket not found'}, status=404)
    return JsonResponse({'ticket': _ticket_json(ticket)})

@csrf_exempt
def add_message_api(request, ticket_id):
    if request.method != 'POST': return JsonResponse({'error': 'POST required'}, status=405)
    user = _user(request)
    if not user: return JsonResponse({'error': 'Telegram authentication required'}, status=401)
    try:
        ticket = add_user_message(ticket_id, user, request.POST.get('content'))
        ticket.refresh_from_db()
        ticket = Ticket.objects.filter(pk=ticket.id).select_related('field','assigned_agent__user').prefetch_related('messages').get()
        return JsonResponse({'ticket': _ticket_json(ticket)})
    except Exception as exc: return JsonResponse({'error': str(exc)}, status=400)

@csrf_exempt
def request_agent_api(request, ticket_id):
    if request.method != 'POST': return JsonResponse({'error': 'POST required'}, status=405)
    user = _user(request)
    if not user: return JsonResponse({'error': 'Telegram authentication required'}, status=401)
    try:
        field = None
        field_id = request.POST.get('field_id')
        if field_id:
            field = SupportField.objects.filter(pk=field_id, active=True).first()
            if not field: raise ValueError('Support field not found.')
        ticket = request_live_agent(ticket_id, user, field)
        ticket = Ticket.objects.filter(pk=ticket.id).select_related('field','assigned_agent__user').prefetch_related('messages').get()
        return JsonResponse({'ticket': _ticket_json(ticket)})
    except Exception as exc: return JsonResponse({'error': str(exc)}, status=400)

@csrf_exempt
def close_ticket_api(request, ticket_id):
    if request.method != 'POST': return JsonResponse({'error': 'POST required'}, status=405)
    user = _user(request)
    if not user: return JsonResponse({'error': 'Telegram authentication required'}, status=401)
    ticket = Ticket.objects.filter(pk=ticket_id, requester=user).first()
    if not ticket: return JsonResponse({'error': 'Ticket not found'}, status=404)
    try:
        ticket = close_ticket_by_user(user, ticket_id)
        ticket = Ticket.objects.filter(pk=ticket.id).select_related('field','assigned_agent__user').prefetch_related('messages').get()
        return JsonResponse({'ticket': _ticket_json(ticket)})
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=400)

def _agent_user(request):
    user = _user(request)
    if not user: return None, JsonResponse({'error': 'Telegram authentication required'}, status=401)
    if not SupportAgent.objects.filter(user=user, active=True).exists(): return None, JsonResponse({'error': 'Support agent access required'}, status=403)
    return user, None

@csrf_exempt
def agent_queue(request):
    user, error = _agent_user(request)
    if error: return error
    agent = SupportAgent.objects.get(user=user, active=True)
    tickets = Ticket.objects.filter(status=Ticket.WAITING_AGENT).select_related('requester','field','related_order').order_by('live_agent_requested_at')[:100]
    mine = Ticket.objects.filter(status=Ticket.ASSIGNED, assigned_agent=agent).select_related('requester','field','related_order').order_by('-updated_at')[:100]
    def row(t):
        return {'id':t.id,'subject':t.subject,'status':t.status,'requester':t.requester.username,'field':t.field.name if t.field else None,'related_order_id':t.related_order_id,'created_at':t.created_at.isoformat(),'updated_at':t.updated_at.isoformat()}
    return JsonResponse({'waiting':[row(t) for t in tickets], 'assigned':[row(t) for t in mine]})

@csrf_exempt
def agent_claim(request, ticket_id):
    if request.method != 'POST': return JsonResponse({'error':'POST required'}, status=405)
    user, error = _agent_user(request)
    if error: return error
    try: return JsonResponse({'ticket': _ticket_json(claim_ticket_manually(user, ticket_id))})
    except Exception as exc: return JsonResponse({'error':str(exc)}, status=400)

@csrf_exempt
def agent_message_api(request, ticket_id):
    if request.method != 'POST': return JsonResponse({'error':'POST required'}, status=405)
    user, error = _agent_user(request)
    if error: return error
    try:
        ticket = add_agent_message(user, ticket_id, request.POST.get('content'))
        ticket = Ticket.objects.filter(pk=ticket.id).select_related('field','assigned_agent__user').prefetch_related('messages').get()
        return JsonResponse({'ticket': _ticket_json(ticket)})
    except Exception as exc: return JsonResponse({'error':str(exc)}, status=400)

@csrf_exempt
def agent_escalate(request, ticket_id):
    if request.method != 'POST': return JsonResponse({'error':'POST required'}, status=405)
    user, error = _agent_user(request)
    if error: return error
    try:
        field = SupportField.objects.get(pk=request.POST.get('field_id'), active=True)
        ticket = escalate_to_field(user, ticket_id, field, request.POST.get('note',''))
        return JsonResponse({'ticket': _ticket_json(ticket)})
    except Exception as exc: return JsonResponse({'error':str(exc)}, status=400)

@csrf_exempt
def agent_resolve(request, ticket_id):
    if request.method != 'POST': return JsonResponse({'error':'POST required'}, status=405)
    user, error = _agent_user(request)
    if error: return error
    try: return JsonResponse({'ticket': _ticket_json(resolve_ticket(user, ticket_id))})
    except Exception as exc: return JsonResponse({'error':str(exc)}, status=400)
