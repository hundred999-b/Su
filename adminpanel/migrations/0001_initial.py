import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
class Migration(migrations.Migration):
    initial=True
    dependencies=[migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[
        migrations.CreateModel(name='StaffRole',fields=[('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),('name',models.CharField(max_length=80,unique=True)),('description',models.CharField(blank=True,max_length=255)),('active',models.BooleanField(default=True)),('permissions',models.JSONField(blank=True,default=list)),('max_approval_amount',models.DecimalField(blank=True,decimal_places=2,max_digits=18,null=True)),('created_at',models.DateTimeField(auto_now_add=True)),('users',models.ManyToManyField(blank=True,related_name='shopu_staff_roles',to=settings.AUTH_USER_MODEL))]),
        migrations.CreateModel(name='StaffAction',fields=[('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),('action',models.CharField(max_length=120)),('object_type',models.CharField(blank=True,max_length=80)),('object_id',models.CharField(blank=True,max_length=80)),('metadata',models.JSONField(blank=True,default=dict)),('created_at',models.DateTimeField(auto_now_add=True)),('actor',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name='shopu_staff_actions',to=settings.AUTH_USER_MODEL))])]
