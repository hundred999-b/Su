from django.urls import path
from . import views

urlpatterns = [
    path('tickets/', views.tickets, name='support-tickets'),
    path('tickets/create/', views.create_ticket_api, name='support-create'),
    path('tickets/<int:ticket_id>/', views.ticket_detail, name='support-ticket'),
    path('tickets/<int:ticket_id>/messages/', views.add_message_api, name='support-message'),
    path('tickets/<int:ticket_id>/agent/', views.request_agent_api, name='support-agent-request'),
    path('tickets/<int:ticket_id>/close/', views.close_ticket_api, name='support-close'),
    path('agent/queue/', views.agent_queue, name='support-agent-queue'),
    path('agent/tickets/<int:ticket_id>/claim/', views.agent_claim, name='support-agent-claim'),
    path('agent/tickets/<int:ticket_id>/messages/', views.agent_message_api, name='support-agent-message'),
    path('agent/tickets/<int:ticket_id>/escalate/', views.agent_escalate, name='support-agent-escalate'),
    path('agent/tickets/<int:ticket_id>/resolve/', views.agent_resolve, name='support-agent-resolve'),
]
