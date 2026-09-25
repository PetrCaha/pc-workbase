import hashlib
import json
from django.core.serializers.json import DjangoJSONEncoder
from django.contrib.auth import get_user_model
from records.models import Customer, Contact, Job, Invoice, JobChange, CustomerChange

def data_digest():
    models=(Customer,Contact,Job,Invoice,JobChange,CustomerChange,get_user_model(),get_user_model().groups.through)
    # Group primary keys may differ across installations; use names for membership.
    data={m._meta.label:list(m.objects.order_by('pk').values()) for m in models[:-1]}
    data['roles']=[(u.username,list(u.groups.order_by('name').values_list('name',flat=True))) for u in get_user_model().objects.order_by('pk')]
    return hashlib.sha256(json.dumps(data,sort_keys=True,ensure_ascii=False,cls=DjangoJSONEncoder).encode()).hexdigest()
