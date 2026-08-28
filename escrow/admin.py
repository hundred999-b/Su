from django.contrib import admin
from adminpanel.admin_mixins import ShopUModelAdmin
from .models import Escrow,PrivateEscrow
@admin.register(Escrow)
class EscrowAdmin(ShopUModelAdmin): list_display=('id','order','amount','currency','status','created_at','released_at'); search_fields=('order__buyer__username','order__product__seller__username'); list_filter=('status','currency')
@admin.register(PrivateEscrow)
class PrivateEscrowAdmin(ShopUModelAdmin): list_display=('escrow_id','seller','buyer','amount','currency','status','created_at'); search_fields=('escrow_id','seller__username','buyer__username'); list_filter=('status','currency')
