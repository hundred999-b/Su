import json
import urllib.request
from django.conf import settings
from django.utils import timezone
from .models import NotificationDelivery

def send_telegram_notification(notification):
    delivery=NotificationDelivery.objects.get(notification=notification)
    delivery.attempts += 1
    token=getattr(settings,"TELEGRAM_NOTIFICATION_BOT_TOKEN","").strip()
    tg=getattr(notification.user,"telegram_account",None)
    chat_id=getattr(tg,"telegram_user_id",None) if tg else None
    if not token or not chat_id:
        delivery.status="skipped"
        delivery.last_error="Telegram credentials or linked account unavailable"
        delivery.save(update_fields=["attempts","status","last_error","updated_at"])
        return False
    payload=json.dumps({"chat_id":chat_id,"text":f"{notification.title}\n\n{notification.message}"}).encode()
    req=urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload,headers={"Content-Type":"application/json"},method="POST")
    try:
        with urllib.request.urlopen(req,timeout=15) as response:
            data=json.loads(response.read().decode())
        if data.get("ok"):
            delivery.status="sent"
            delivery.telegram_message_id=str(data.get("result",{}).get("message_id",""))
            delivery.sent_at=timezone.now()
            delivery.last_error=""
        else:
            delivery.status="failed"
            delivery.last_error=str(data)
        delivery.save(update_fields=["attempts","status","telegram_message_id","sent_at","last_error","updated_at"])
        return data.get("ok",False)
    except Exception as exc:
        delivery.status="failed"
        delivery.last_error=str(exc)
        delivery.save(update_fields=["attempts","status","last_error","updated_at"])
        return False

def notify(user,kind,title,message):
    from telegram_integration.models import Notification
    n=Notification.objects.create(user=user,kind=kind,title=title,message=message)
    from .services import queue_telegram_notification
    queue_telegram_notification(n)
    send_telegram_notification(n)
    return n
