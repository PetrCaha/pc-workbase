"""Bind and validate existing forms without invoking save() or audit writes."""
from django.shortcuts import get_object_or_404, render
from django.utils.translation import gettext as _
from records.forms import CustomerForm, ContactForm, JobForm, JobTransferForm, InvoiceForm
from records.models import Customer, Contact, Job, Invoice
from records.permissions import ROLE_ADMIN

def preview_form(request, route, params):
    posted = request.method == 'POST'
    data = request.POST if posted else None
    job = None
    cancel_url = '/'
    if route.startswith('customer-'):
        obj = get_object_or_404(Customer, pk=params['pk']) if params.get('pk') else None
        form = CustomerForm(data, instance=obj)
        title = _('Upravit zákazníka') if obj else _('Nový zákazník')
        cancel_url = obj.get_absolute_url() if obj else '/zakaznici/'
    elif route.startswith('contact-'):
        customer = get_object_or_404(Customer, pk=params['customer_pk'])
        obj = get_object_or_404(Contact, pk=params['pk'], customer=customer) if params.get('pk') else None
        form = ContactForm(data, instance=obj)
        # Validation can inspect the correct parent but never save the model.
        form.instance.customer = customer
        title = _('Upravit kontakt') if obj else _('Nový kontakt')
        cancel_url = customer.get_absolute_url()
    elif route.startswith('invoice-'):
        job = get_object_or_404(Job, pk=params['job_pk'])
        obj = get_object_or_404(Invoice, pk=params['invoice_pk'], job=job) if params.get('invoice_pk') else None
        form = InvoiceForm(data, instance=obj)
        title = _('Upravit fakturu') if obj else _('Nová faktura')
        cancel_url = job.get_absolute_url() + '#faktury'
    else:
        job = get_object_or_404(Job, pk=params['pk']) if params.get('pk') else None
        if route == 'job-transfer':
            form = JobTransferForm(data, instance=job)
            title = _('Změnit zákazníka zakázky')
        else:
            initial = {}
            if not job and request.GET.get('customer', '').isdigit():
                initial['customer'] = request.GET['customer']
            form = JobForm(data, instance=job, initial=initial, role=ROLE_ADMIN)
            title = _('Upravit zakázku') if job else _('Nová zakázka')
        cancel_url = job.get_absolute_url() if job else '/zakazky/'
    if not posted:
        for field in ('title', 'description', 'note', 'items_text', 'supplier_address', 'customer_header', 'payment_method'):
            if form.initial.get(field):
                form.initial[field] = _(str(form.initial[field]))
    if posted:
        form.is_valid()
    return render(request, 'records/form.html', {'form': form, 'title': title, 'job': job, 'cancel_url': cancel_url, 'demo_submitted': posted, 'job_form': route in ('job-create', 'job-update')})
