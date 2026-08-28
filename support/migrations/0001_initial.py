import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SupportField',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=80, unique=True)),
                ('description', models.CharField(blank=True, max_length=255)),
                ('active', models.BooleanField(default=True)),
            ],
        ),
        migrations.CreateModel(
            name='SupportSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('singleton', models.BooleanField(default=True, editable=False, unique=True)),
                ('max_open_tickets_per_agent', models.PositiveIntegerField(default=7)),
                ('agent_response_timeout_minutes', models.PositiveIntegerField(default=15)),
                ('closing_message', models.TextField(default="This ticket is now being closed. Thanks for reaching out — reply anytime to open a new one if you need further help.")),
                ('expiry_message', models.TextField(default="We didn't hear back from you in time, so this support session has expired and you've been removed from the queue. Feel free to reach out again whenever you're ready.")),
                ('queue_notice_message', models.TextField(default="You've been added to the live agent queue. Heads up: once an agent is matched to you, you'll need to respond within the response window or you'll be removed from the queue and will need to request an agent again.")),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='KnowledgeEntry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('trigger_keywords', models.CharField(help_text="Comma-separated keywords/phrases. Case-insensitive substring match against the user's message. e.g. 'refund, money back, didn't receive'", max_length=500)),
                ('response', models.TextField()),
                ('priority', models.IntegerField(default=0, help_text='Higher priority entries are checked first when multiple match.')),
                ('active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('field', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='knowledge_entries', to='support.supportfield')),
            ],
            options={'ordering': ['-priority', 'id']},
        ),
        migrations.CreateModel(
            name='SupportAgent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_available', models.BooleanField(default=True, help_text='Turn off to stop receiving new tickets without removing the agent.')),
                ('max_open_tickets_override', models.PositiveIntegerField(blank=True, help_text='Leave blank to use the global default from Support Settings.', null=True)),
                ('active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('fields', models.ManyToManyField(blank=True, related_name='agents', to='support.supportfield')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='support_agent_profile', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Ticket',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('subject', models.CharField(blank=True, max_length=200)),
                ('status', models.CharField(choices=[('open', 'Open — bot handling'), ('waiting_agent', 'Waiting for a live agent'), ('assigned', 'Assigned to an agent'), ('resolved', 'Resolved'), ('closed', 'Closed'), ('expired', 'Expired — no response')], default='open', max_length=20)),
                ('requested_live_agent', models.BooleanField(default=False)),
                ('live_agent_requested_at', models.DateTimeField(blank=True, null=True)),
                ('claimed_at', models.DateTimeField(blank=True, null=True)),
                ('response_deadline', models.DateTimeField(blank=True, help_text='Requester must send a message by this time or the ticket auto-expires.', null=True)),
                ('resolved_at', models.DateTimeField(blank=True, null=True)),
                ('closed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('assigned_agent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='tickets', to='support.supportagent')),
                ('field', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='tickets', to='support.supportfield')),
                ('requester', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='support_tickets', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddIndex(
            model_name='ticket',
            index=models.Index(fields=['status', 'response_deadline'], name='support_tic_status_2f6d59_idx'),
        ),
        migrations.AddIndex(
            model_name='ticket',
            index=models.Index(fields=['status', 'created_at'], name='support_tic_status_7c9a1a_idx'),
        ),
        migrations.CreateModel(
            name='TicketMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(choices=[('bot', 'Bot'), ('user', 'Requester'), ('agent', 'Agent'), ('system', 'System')], max_length=10)),
                ('content', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('sender', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('ticket', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='support.ticket')),
            ],
            options={'ordering': ['created_at']},
        ),
    ]
