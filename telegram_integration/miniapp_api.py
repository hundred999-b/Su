from decimal import Decimal
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Avg, Q
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from marketplace.models import Product, Order
from marketplace.services import get_active_listing_policy, publish_listing, purchase_product, mark_order_delivered, confirm_order as confirm_marketplace_order, open_dispute
from escrow.models import Escrow, PrivateEscrow
from escrow.services import release_escrow, refund_escrow, fund_private_escrow, release_private_escrow
from ledger.transaction_service import purchase_order, wallet_balance
from reviews.models import Review
from reviews.services import create_review, edit_review
from vendor_verification.services import get_vendor_verification
from vendor_verification.trust import vendor_badges
from vendor_verification.models import VendorComplaint
from accounts.models import Profile
from stage4.models import TermsDocument
from stage4.services import require_terms, accept_terms
from .models import Notification
from support.models import SupportAgent
from .shopu_auth import authenticate_init_data
from uuid import uuid4
from PIL import Image
from django.core.files.uploadedfile import UploadedFile
User=get_user_model()

def _user(request):
    return authenticate_init_data(request.POST.get('init_data') or request.GET.get('init_data'))

def _presence(user):
    p=getattr(user,'profile',None); now=timezone.now()
    active=bool(p and p.presence_enabled and p.last_seen_at and (now-p.last_seen_at).total_seconds()<=300 and not p.suspended)
    return 'active_now' if active else 'offline'

def _image_url(request, field):
    return request.build_absolute_uri(field.url) if field else None

def _validate_image(upload, label='image', max_bytes=5 * 1024 * 1024):
    if not upload or not isinstance(upload, UploadedFile):
        return
    if upload.size > max_bytes:
        raise ValueError(f'{label.title()} must be 5 MB or smaller.')
    try:
        image = Image.open(upload)
        image.verify()
        upload.seek(0)
        image = Image.open(upload)
        if image.format not in {'JPEG', 'PNG', 'WEBP'}:
            raise ValueError(f'{label.title()} must be JPEG, PNG, or WebP.')
        if image.width > 5000 or image.height > 5000:
            raise ValueError(f'{label.title()} dimensions are too large.')
        upload.seek(0)
    except ValueError:
        raise
    except Exception:
        raise ValueError(f'Invalid {label}.')

def _profile_json(request, user):
    profile, _ = Profile.objects.get_or_create(user=user)
    return {
        'id': user.id, 'username': user.username, 'role': profile.role,
        'status': _presence(user), 'profile_image': _image_url(request, profile.profile_image),
    }

def _product_json(request,p):
    cache = getattr(request, '_vendor_trust_cache', None)
    if cache is None:
        cache = request._vendor_trust_cache = {}
    trust = cache.get(p.seller_id)
    if trust is None:
        trust = vendor_badges(p.seller)
        cache[p.seller_id] = trust
    return {
        'id':p.id,'name':p.title,'description':p.description,'category':p.category,
        'price':str(p.price),'currency':p.currency,'seller':p.seller.username,'seller_id':p.seller_id,
        'seller_status':_presence(p.seller),
        'seller_image':_image_url(request, getattr(getattr(p.seller, 'profile', None), 'profile_image', None)),
        'image':_image_url(request,p.image),'condition':p.condition,'seller_terms':p.seller_terms,
        'listing_version':p.version,'trust':trust,
    }

@csrf_exempt
def bootstrap(request):
    user=_user(request)
    if not user: return JsonResponse({'error':'Telegram authentication required'},status=401)
    unread=Notification.objects.filter(user=user,read=False).count()
    return JsonResponse({'app':'ShopU','user':_profile_json(request,user),'is_support_agent':SupportAgent.objects.filter(user=user, active=True).exists(),'wallets':[], 'unread_notifications':unread})

def products(request):
    q=request.GET.get('q','').strip(); category=request.GET.get('category','').strip()
    qs=Product.objects.select_related('seller').filter(active=True)
    if q: qs=qs.filter(Q(title__icontains=q)|Q(description__icontains=q)|Q(seller__username__icontains=q))
    if category: qs=qs.filter(category__iexact=category)
    return JsonResponse({'products':[_product_json(request,p) for p in qs.order_by('-id')[:100]],'categories':list(Product.objects.filter(active=True).exclude(category='').values_list('category',flat=True).distinct().order_by('category'))})

@csrf_exempt
def profile(request):
    user = _user(request)
    if not user: return JsonResponse({'error':'Telegram authentication required'}, status=401)
    return JsonResponse({'profile': _profile_json(request, user)})

@csrf_exempt
def profile_photo(request):
    if request.method != 'POST': return JsonResponse({'error':'POST required'}, status=405)
    user = _user(request)
    if not user: return JsonResponse({'error':'Telegram authentication required'}, status=401)
    upload = request.FILES.get('image')
    try:
        if not upload: raise ValueError('Choose a profile photo first.')
        _validate_image(upload, 'profile photo')
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.profile_image = upload
        profile.save(update_fields=['profile_image'])
        return JsonResponse({'success':True, 'profile':_profile_json(request,user)})
    except Exception as exc:
        return JsonResponse({'error':str(exc)}, status=400)

@csrf_exempt
def listing_policy(request):
    policy = get_active_listing_policy()
    return JsonResponse({
        "title": policy.title,
        "version": policy.version,
        "content": policy.content,
    })


@csrf_exempt
def buyer_terms(request):
    """
    Return the currently active ShopU Buyer Terms.
    """
    if request.method != 'GET':
        return JsonResponse({'error': 'GET required'}, status=405)

    user = _user(request)
    if not user:
        return JsonResponse(
            {'error': 'Telegram authentication required'},
            status=401,
        )

    terms = TermsDocument.objects.filter(
        kind=TermsDocument.BUYER,
        active=True,
    ).order_by('-created_at').first()

    if not terms:
        return JsonResponse(
            {'error': 'No active buyer terms are configured'},
            status=503,
        )

    user = _user(request)
    accepted = bool(
        user and
        terms.acceptances.filter(user=user).exists()
    )

    return JsonResponse({
        'title': terms.title,
        'version': terms.version,
        'body': terms.body,
        'active': terms.active,
        'accepted': accepted,
    })


@csrf_exempt
def accept_buyer_terms(request):
    """
    Record explicit acceptance of the currently active Buyer Terms.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    user = _user(request)
    if not user:
        return JsonResponse(
            {'error': 'Telegram authentication required'},
            status=401,
        )

    terms = TermsDocument.objects.filter(
        kind=TermsDocument.BUYER,
        active=True,
    ).order_by('-created_at').first()

    if not terms:
        return JsonResponse(
            {'error': 'No active buyer terms are configured'},
            status=503,
        )

    # The client must explicitly confirm that the displayed terms
    # were reviewed before acceptance.
    if request.POST.get('accepted') != 'true':
        return JsonResponse(
            {'error': 'You must explicitly accept the current Buyer Terms.'},
            status=400,
        )

    acceptance = accept_terms(
        user,
        terms,
        request=request,
        purpose='purchase',
    )

    return JsonResponse({
        'success': True,
        'accepted': True,
        'terms': {
            'title': terms.title,
            'version': terms.version,
        },
        'accepted_at': acceptance.accepted_at.isoformat(),
    })


@csrf_exempt
def create_product_api(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    user = _user(request)
    if not user:
        return JsonResponse({'error': 'Telegram authentication required'}, status=401)
    try:
        from decimal import Decimal
        data = {
            'title': request.POST.get('title', ''),
            'description': request.POST.get('description', ''),
            'category': request.POST.get('category', ''),
            'condition': request.POST.get('condition', ''),
            'seller_terms': request.POST.get('seller_terms', ''),
            'price': Decimal(request.POST.get('price', '0')),
            'currency': request.POST.get('currency', 'USD'),
            'disclosure_acknowledged': request.POST.get('disclosure_acknowledged') == 'true',
            'fee_acknowledged': request.POST.get('fee_acknowledged') == 'true',
            'image': request.FILES.get('image'),
        }
        _validate_image(data.get('image'), 'listing photo')
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.role = Profile.SELLER
        profile.save(update_fields=['role'])
        product = publish_listing(seller=user, data=data)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'success': True, 'product': _product_json(request, product)}, status=201)


@csrf_exempt
def buy_product(request, product_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    buyer = _user(request)
    if not buyer:
        return JsonResponse({'error': 'Telegram authentication required'}, status=401)
    try:
        order, tx = purchase_product(
            buyer=buyer,
            product_id=product_id,
            disclosure_acknowledged=request.POST.get('disclosure_acknowledged') == 'true',
            idempotency_key=request.headers.get('Idempotency-Key') or request.POST.get('idempotency_key'),
        )
    except PermissionError as e:
        return JsonResponse({'error': str(e)}, status=403)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)

    if not getattr(order, '_idempotent_replay', False):
        Notification.objects.create(
            user=order.product.seller,
            kind='order',
            title='New order',
            message=f'Order #{order.id} was funded into escrow.',
        )
        Notification.objects.create(
            user=buyer,
            kind='order',
            title='Purchase secured',
            message=f'Order #{order.id} is now held in ShopU escrow.',
        )
    return JsonResponse({
        'success': True,
        'order_id': order.id,
        'status': order.status,
        'transaction_id': tx.transaction_id,
        'listing_version': order.listing_version,
    })

@csrf_exempt
def mark_delivered(request, order_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    seller = _user(request)
    if not seller:
        return JsonResponse({'error': 'Telegram authentication required'}, status=401)
    try:
        order = mark_order_delivered(
            order_id=order_id,
            seller=seller,
            auto_release_hours=getattr(
                __import__('django.conf', fromlist=['settings']).settings,
                'SHOPU_AUTO_RELEASE_HOURS', 6
            ),
        )
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=404)
    Notification.objects.create(
        user=order.buyer,
        kind='delivery',
        title='Order delivered',
        message=f'Order #{order.id} was marked delivered. Confirm receipt or raise a dispute before the deadline.',
    )
    return JsonResponse({
        'success': True,
        'deadline': order.confirmation_deadline.isoformat(),
    })

@csrf_exempt
def confirm_order(request, order_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    buyer = _user(request)
    if not buyer:
        return JsonResponse({'error': 'Telegram authentication required'}, status=401)
    try:
        order, tx = confirm_marketplace_order(order_id=order_id, buyer=buyer)
    except PermissionError as e:
        return JsonResponse({'error': str(e)}, status=403)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)

    Notification.objects.create(
        user=order.product.seller,
        kind='escrow',
        title='Funds released',
        message=f'Order #{order.id} was confirmed and funds were released.',
    )
    return JsonResponse({
        'success': True,
        'status': 'completed',
        'transaction_id': tx.transaction_id,
    })

@csrf_exempt
def dispute_order(request, order_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    user = _user(request)
    if not user:
        return JsonResponse({'error': 'Telegram authentication required'}, status=401)
    message = request.POST.get('message', 'Buyer/seller opened a dispute.')
    try:
        order, event = open_dispute(
            order_id=order_id, actor=user, message=message
        )
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)
    Notification.objects.create(
        user=order.product.seller,
        title='Dispute opened',
        kind='dispute',
        message=f'Order #{order.id} has been placed into dispute.',
    )
    Notification.objects.create(
        user=order.buyer,
        title='Dispute opened',
        kind='dispute',
        message=f'Order #{order.id} has been placed into dispute.',
    )
    return JsonResponse({
        'success': True,
        'status': order.status,
        'event_id': event.id,
    })

def orders(request):
    user=_user(request)
    if not user:return JsonResponse({'error':'Telegram authentication required'},status=401)
    from reviews.models import Review
    from stage4.models import DisputeEvent
    qs=Order.objects.filter(Q(buyer=user)|Q(product__seller=user)).select_related('product','product__seller').order_by('-id')[:100]

    def review_state(o):
        if o.buyer_id != user.id:
            return False, None, None
        existing = Review.objects.filter(order=o).first()
        if existing:
            return False, existing.id, None
        if o.status == Order.COMPLETED:
            return True, None, None
        if o.status == Order.DISPUTED:
            return False, None, 'Review becomes available if the dispute is resolved in your favor.'
        if o.status == Order.REFUNDED:
            buyer_favor = DisputeEvent.objects.filter(
                order=o,
                event_type='resolved',
                metadata__outcome='buyer_favor',
            ).exists()
            if buyer_favor:
                return True, None, None
        return False, None, None

    payload=[]
    for o in qs:
        can_review, review_id, review_locked_reason = review_state(o)
        payload.append({
            'id':o.id,
            'product':o.product.title,
            'amount':str(o.amount),
            'currency':o.currency,
            'status':o.status,
            'role':'buyer' if o.buyer_id==user.id else 'seller',
            'deadline':o.confirmation_deadline.isoformat() if o.confirmation_deadline else None,
            'can_confirm':o.buyer_id==user.id and o.status==Order.DELIVERED,
            'can_deliver':o.product.seller_id==user.id and o.status==Order.ESCROW,
            'can_dispute':o.status in [Order.ESCROW,Order.DELIVERED],
            'can_review':can_review,
            'review_id':review_id,
            'review_locked_reason':review_locked_reason,
        })
    return JsonResponse({'orders':payload})

@csrf_exempt
def create_private_escrow(request):
    if request.method!='POST':return JsonResponse({'error':'POST required'},status=405)
    seller=_user(request)
    if not seller:return JsonResponse({'error':'Telegram authentication required'},status=401)
    try: amount=Decimal(request.POST.get('amount','0'))
    except: return JsonResponse({'error':'Invalid amount'},status=400)
    if amount<=0:return JsonResponse({'error':'Amount must be greater than zero'},status=400)
    eid='SU-'+uuid4().hex[:12].upper()
    e=PrivateEscrow.objects.create(escrow_id=eid,seller=seller,title=request.POST.get('title','Private transaction').strip()[:200],description=request.POST.get('description','').strip(),amount=amount,currency=request.POST.get('currency','USD').upper())
    return JsonResponse({'success':True,'escrow_id':e.escrow_id,'status':e.status})

def private_escrow(request,escrow_id):
    user = _user(request)
    if not user:
        return JsonResponse(
            {'error': 'Telegram authentication required'},
            status=401,
        )

    e = (
        PrivateEscrow.objects
        .filter(escrow_id=escrow_id)
        .select_related('seller','buyer')
        .first()
    )

    if not e:
        return JsonResponse({'error':'Escrow not found'},status=404)

    # Private escrow details are visible only to its participants.
    # This prevents escrow-ID enumeration from leaking transaction data.
    if e.seller_id != user.id and e.buyer_id != user.id:
        return JsonResponse({'error':'Escrow not found'},status=404)

    return JsonResponse({
        'escrow': {
            'id': e.escrow_id,
            'title': e.title,
            'description': e.description,
            'amount': str(e.amount),
            'currency': e.currency,
            'status': e.status,
            'seller': e.seller.username,
            'buyer': e.buyer.username if e.buyer else None,
        }
    })

@csrf_exempt
def fund_private(request,escrow_id):
    if request.method!='POST': return JsonResponse({'error':'POST required'},status=405)
    buyer=_user(request)
    if not buyer: return JsonResponse({'error':'Telegram authentication required'},status=401)
    try: tx=fund_private_escrow(escrow_id,buyer)
    except Exception as e: return JsonResponse({'error':str(e)},status=400)
    e=PrivateEscrow.objects.get(escrow_id=escrow_id); Notification.objects.create(user=e.seller,kind='escrow',title='Private escrow funded',message=f'{e.escrow_id} is funded and protected.')
    return JsonResponse({'success':True,'status':e.status,'transaction_id':tx.transaction_id,'deadline':e.deadline.isoformat() if e.deadline else None})

@csrf_exempt
def release_private(request,escrow_id):
    if request.method!='POST': return JsonResponse({'error':'POST required'},status=405)
    buyer=_user(request)
    if not buyer: return JsonResponse({'error':'Telegram authentication required'},status=401)
    e=PrivateEscrow.objects.filter(escrow_id=escrow_id,buyer=buyer).first()
    if not e:return JsonResponse({'error':'Escrow not found'},status=404)
    try: tx=release_private_escrow(escrow_id,actor=buyer)
    except Exception as ex:return JsonResponse({'error':str(ex)},status=400)
    Notification.objects.create(user=e.seller,kind='escrow',title='Private escrow released',message=f'{e.escrow_id} was released by the buyer.')
    return JsonResponse({'success':True,'status':'released','transaction_id':tx.transaction_id})

@csrf_exempt
@transaction.atomic
def join_private_escrow(request, escrow_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    buyer = _user(request)
    if not buyer:
        return JsonResponse({'error': 'Telegram authentication required'}, status=401)
    e = PrivateEscrow.objects.select_for_update().filter(
        escrow_id=escrow_id,
        status=PrivateEscrow.CREATED,
        buyer__isnull=True,
    ).first()
    if not e:
        return JsonResponse({'error': 'Escrow unavailable'}, status=404)
    if e.seller_id == buyer.id:
        return JsonResponse({'error': 'Seller cannot join as buyer'}, status=400)
    e.buyer = buyer
    e.save(update_fields=['buyer'])
    Notification.objects.create(
        user=e.seller, kind='escrow', title='Buyer joined escrow',
        message=f'{buyer.username} joined {e.escrow_id}.'
    )
    return JsonResponse({
        'success': True, 'escrow_id': e.escrow_id, 'status': e.status
    })

@csrf_exempt
@transaction.atomic
def mark_private_delivered(request, escrow_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    seller = _user(request)
    if not seller:
        return JsonResponse({'error': 'Telegram authentication required'}, status=401)
    e = PrivateEscrow.objects.select_for_update().filter(
        escrow_id=escrow_id, seller=seller, status=PrivateEscrow.FUNDED
    ).first()
    if not e:
        return JsonResponse(
            {'error': 'Private escrow not found or not funded'}, status=404
        )
    e.status = PrivateEscrow.DELIVERED
    e.delivered_at = timezone.now()
    hours = getattr(
        __import__('django.conf', fromlist=['settings']).settings,
        'SHOPU_AUTO_RELEASE_HOURS', 6
    )
    e.deadline = timezone.now() + __import__('datetime').timedelta(hours=hours)
    e.save(update_fields=['status', 'delivered_at', 'deadline'])
    from adminpanel.jobs import enqueue_job
    enqueue_job(
        "escrow.auto_release",
        dedupe_key=f"escrow:auto-release:private:{e.escrow_id}",
        payload={"private_escrow_id": e.escrow_id},
        run_after=e.deadline,
    )
    if e.buyer_id:
        Notification.objects.create(
            user=e.buyer, kind='delivery', title='Private escrow delivered',
            message=f'{e.escrow_id} was marked delivered. Confirm receipt before the deadline.'
        )
    return JsonResponse({
        'success': True, 'status': e.status,
        'deadline': e.deadline.isoformat()
    })


def vendor_profile(request, seller_id):
    seller = User.objects.filter(id=seller_id).first()
    if not seller:
        return JsonResponse({'error': 'Vendor not found'}, status=404)
    from django.db.models import Count
    from stage4.models import DisputeEvent
    v = getattr(seller, 'vendor_verification', None)
    qs = Review.objects.filter(seller=seller, visible=True)
    avg = qs.aggregate(a=Avg('rating'))['a']
    orders = Order.objects.filter(product__seller=seller)
    completed = orders.filter(status=Order.COMPLETED).count()
    buyer_disputes = DisputeEvent.objects.filter(order__buyer=seller, event_type='opened').count()
    active_listings = seller.products.filter(active=True).count()
    refunded = orders.filter(status=Order.REFUNDED).count()
    trust = vendor_badges(seller)
    disputed = trust['metrics']['dispute_count']
    return JsonResponse({
        'seller': {'id': seller.id, 'username': seller.username, 'status': _presence(seller), 'profile_image': _image_url(request, getattr(getattr(seller, 'profile', None), 'profile_image', None))},
        'verification': {'status': v.status if v else 'unverified', 'badge': v.badge if v else '', 'badge_level': v.badge_level if v else 'unverified'},
        'trust': trust,
        'stats': {
            'completed_transactions': completed,
            'total_orders': orders.count(),
            'active_listings': active_listings,
            'review_count': qs.count(),
            'average_rating': round(float(avg), 2) if avg else None,
            'dispute_count': disputed,
            'disputes_against_vendor': disputed,
            'disputes_as_buyer': buyer_disputes,
            'refunded_orders': refunded,
            'dispute_rate_percent': round((disputed / completed) * 100, 2) if completed else 0,
        },
        'reviews': [
            {'id': r.id, 'buyer': r.buyer.username, 'rating': r.rating, 'comment': r.comment, 'edited': r.edited, 'created_at': r.created_at.isoformat()}
            for r in qs.select_related('buyer')[:50]
        ],
    })


@csrf_exempt
def report_vendor(request, seller_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    reporter = _user(request)
    if not reporter:
        return JsonResponse({'error': 'Telegram authentication required'}, status=401)
    seller = User.objects.filter(pk=seller_id).first()
    if not seller:
        return JsonResponse({'error': 'Vendor not found'}, status=404)
    if seller.id == reporter.id:
        return JsonResponse({'error': 'You cannot report your own seller profile.'}, status=400)
    seller_profile = getattr(seller, 'profile', None)
    if not seller_profile or seller_profile.role != Profile.SELLER:
        return JsonResponse({'error': 'This account is not registered as a seller.'}, status=400)
    description = (request.POST.get('description') or '').strip()
    if len(description) < 20:
        return JsonResponse({'error': 'Please provide at least 20 characters describing the issue.'}, status=400)
    if len(description) > 10000:
        return JsonResponse({'error': 'Complaint is too long.'}, status=400)
    category = (request.POST.get('category') or 'other').strip()[:60] or 'other'
    order = None
    order_id = request.POST.get('order_id')
    if order_id:
        order = Order.objects.filter(pk=order_id, buyer=reporter, product__seller=seller).first()
        if not order:
            return JsonResponse({'error': 'The selected order does not belong to this seller.'}, status=400)
    recent_cutoff = timezone.now() - timedelta(hours=24)
    duplicate = VendorComplaint.objects.filter(
        seller=seller, reporter=reporter, status__in=[VendorComplaint.OPEN, VendorComplaint.SUBSTANTIATED],
        created_at__gte=recent_cutoff,
    ).exists()
    if duplicate:
        return JsonResponse({'error': 'You already have a recent open complaint against this seller.'}, status=409)
    complaint = VendorComplaint.objects.create(
        seller=seller, reporter=reporter, order=order, category=category, description=description,
    )
    return JsonResponse({'success': True, 'complaint_id': complaint.id, 'message': 'Report submitted for ShopU review.'}, status=201)

@csrf_exempt
def create_review_api(request):
    if request.method!='POST':return JsonResponse({'error':'POST required'},status=405)
    buyer=_user(request)
    if not buyer:return JsonResponse({'error':'Telegram authentication required'},status=401)
    try:r=create_review(buyer=buyer,order_id=int(request.POST['order_id']),rating=int(request.POST['rating']),comment=request.POST.get('comment',''))
    except Exception as e:return JsonResponse({'error':str(e)},status=400)
    return JsonResponse({'success':True,'review':{'id':r.id,'rating':r.rating,'comment':r.comment}})

@csrf_exempt
def edit_review_api(request,review_id):
    if request.method!='POST':return JsonResponse({'error':'POST required'},status=405)
    buyer=_user(request)
    if not buyer:return JsonResponse({'error':'Telegram authentication required'},status=401)
    try:r=edit_review(buyer=buyer,review_id=review_id,rating=int(request.POST['rating']),comment=request.POST.get('comment',''))
    except Exception as e:return JsonResponse({'error':str(e)},status=400)
    return JsonResponse({'success':True,'review':{'id':r.id,'rating':r.rating,'comment':r.comment,'edited':r.edited}})

def notifications(request):
    user=_user(request)
    if not user:return JsonResponse({'error':'Telegram authentication required'},status=401)
    return JsonResponse({'notifications':[{'id':n.id,'title':n.title,'message':n.message,'kind':n.kind,'read':n.read,'created_at':n.created_at.isoformat()} for n in Notification.objects.filter(user=user).order_by('-id')[:100]]})

@csrf_exempt
def mark_notification_read(request,notification_id):
    user=_user(request)
    if not user:return JsonResponse({'error':'Telegram authentication required'},status=401)
    Notification.objects.filter(id=notification_id,user=user).update(read=True)
    return JsonResponse({'success':True})
