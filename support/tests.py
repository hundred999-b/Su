from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from accounts.models import Profile
from marketplace.models import Order, Product

from .models import SupportAgent, SupportField, SupportSettings, Ticket, TicketMessage
from .services import add_agent_message, add_user_message, claim_ticket_manually, create_ticket, request_live_agent, resolve_ticket


class SupportServiceTests(TestCase):
    def setUp(self):
        SupportSettings.objects.get_or_create(pk=1)
        self.buyer = User.objects.create_user('buyer', password='x')
        self.seller = User.objects.create_user('seller', password='x')
        Profile.objects.create(user=self.buyer)
        Profile.objects.create(user=self.seller, role=Profile.SELLER)
        self.agent_user = User.objects.create_user('agent', password='x', is_staff=True)
        self.field = SupportField.objects.create(name='Payments')
        self.agent = SupportAgent.objects.create(user=self.agent_user)
        self.agent.fields.add(self.field)
        self.product = Product.objects.create(
            seller=self.seller, title='Test product', description='A sufficiently detailed test listing.',
            price='10.00', currency='USD', seller_terms='Returns subject to ShopU rules.',
        )
        self.order = Order.objects.create(
            buyer=self.buyer, product=self.product, amount='10.00', currency='USD',
        )

    def test_create_ticket_and_bot_message(self):
        ticket = create_ticket(self.buyer, 'I need help with my order', 'Order help', related_order=self.order)
        self.assertEqual(ticket.requester_id, self.buyer.id)
        self.assertEqual(ticket.related_order_id, self.order.id)
        self.assertTrue(ticket.messages.filter(role=TicketMessage.USER).exists())

    def test_order_link_requires_participant(self):
        other = User.objects.create_user('other', password='x')
        with self.assertRaises(ValueError):
            create_ticket(other, 'Help', related_order=self.order)

    def test_user_message_rejects_empty(self):
        ticket = create_ticket(self.buyer, 'Initial')
        with self.assertRaises(ValueError):
            add_user_message(ticket.pk, self.buyer, '   ')

    def test_agent_assignment_and_reply(self):
        ticket = create_ticket(self.buyer, 'I need a human')
        request_live_agent(ticket.pk, self.buyer, self.field)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, Ticket.ASSIGNED)
        add_agent_message(self.agent_user, ticket.pk, 'I am checking this for you.')
        self.assertTrue(ticket.messages.filter(role=TicketMessage.AGENT).exists())

    def test_agent_capacity_is_enforced(self):
        SupportSettings.objects.filter(pk=1).update(max_open_tickets_per_agent=1)
        first = create_ticket(self.buyer, 'first')
        request_live_agent(first.pk, self.buyer)
        second = create_ticket(self.buyer, 'second')
        request_live_agent(second.pk, self.buyer)
        self.assertEqual(Ticket.objects.filter(assigned_agent=self.agent, status=Ticket.ASSIGNED).count(), 1)
        self.assertEqual(Ticket.objects.filter(status=Ticket.WAITING_AGENT).count(), 1)

    def test_resolve_frees_capacity(self):
        ticket = create_ticket(self.buyer, 'human')
        request_live_agent(ticket.pk, self.buyer)
        resolve_ticket(self.agent_user, ticket.pk)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, Ticket.RESOLVED)
        self.assertIsNone(ticket.response_deadline)

    def test_user_cannot_reply_to_other_ticket(self):
        ticket = create_ticket(self.buyer, 'Private')
        with self.assertRaises(ValueError):
            add_user_message(ticket.pk, self.seller, 'Nope')

    def test_closed_ticket_cannot_receive_messages(self):
        ticket = create_ticket(self.buyer, 'Close me')
        ticket.status = Ticket.CLOSED
        ticket.save(update_fields=['status'])
        with self.assertRaises(ValueError):
            add_user_message(ticket.pk, self.buyer, 'Still here')
