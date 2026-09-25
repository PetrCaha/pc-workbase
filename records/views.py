from django.utils.translation import gettext as _
import csv
import json
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
from xml.sax.saxutils import escape

from django.contrib import messages
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Case, Count, IntegerField, Q, Sum, When
from django.http import FileResponse, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .forms import AppUserCreationForm, AppUserUpdateForm, ContactForm, CustomerForm, InvoiceForm, InvoiceUploadForm, JobForm, JobTransferForm
from .invoice_ocr import InvoiceScanError, extract_invoice_data, parse_invoice_text
from .models import Contact, Customer, CustomerChange, Invoice, Job, JobChange
from .permissions import ROLE_ADMIN, ROLE_MANAGER, ROLE_MEMBER, get_role_label, get_user_role, has_role, roles_required


TRACKED_JOB_FIELDS = ['responsible', 'contact', 'title', 'description', 'status', 'due_date', 'completed_at', 'price']
TRACKED_CUSTOMER_FIELDS = ['name', 'company_id', 'email', 'phone', 'street', 'city', 'postal_code', 'status', 'note']
TRACKED_CONTACT_FIELDS = ['name', 'role', 'phone', 'email', 'is_primary', 'note']
TRACKED_INVOICE_FIELDS = [
    'supplier_name', 'supplier_company_id', 'supplier_address', 'customer_header',
    'invoice_number', 'variable_symbol', 'issue_date', 'taxable_date', 'due_date',
    'payment_method', 'items_text', 'subtotal', 'vat_amount', 'total_amount',
    'currency', 'note',
]


def _job_value(job, field_name):
    if field_name == 'status':
        return job.get_status_display()
    value = getattr(job, field_name)
    return str(value) if value not in (None, '') else '—'


def _job_changes(before, after, fields=None):
    result = {}
    for field_name in fields or TRACKED_JOB_FIELDS:
        old_value = _job_value(before, field_name)
        new_value = _job_value(after, field_name)
        if old_value != new_value:
            label = str(Job._meta.get_field(field_name).verbose_name)
            result[label] = {'from': old_value, 'to': new_value}
    return result


def _audit_value(instance, field_name):
    display = getattr(instance, f'get_{field_name}_display', None)
    if callable(display):
        return str(display())
    value = getattr(instance, field_name)
    if isinstance(value, bool):
        return _('Ano') if value else _('Ne')
    return str(value) if value not in (None, '') else '—'


def _model_changes(before, after, fields):
    result = {}
    for field_name in fields:
        old_value = _audit_value(before, field_name)
        new_value = _audit_value(after, field_name)
        if old_value != new_value:
            label = str(after._meta.get_field(field_name).verbose_name)
            result[label] = {'from': old_value, 'to': new_value}
    return result


def _deleted_contact_values(contact):
    result = {}
    for field_name in TRACKED_CONTACT_FIELDS:
        value = _audit_value(contact, field_name)
        if value != '—':
            label = str(contact._meta.get_field(field_name).verbose_name)
            result[label] = {'from': value, 'to': _('odstraněno')}
    return result


def _deleted_invoice_values(invoice):
    result = {}
    for field_name in TRACKED_INVOICE_FIELDS:
        value = _audit_value(invoice, field_name)
        if value != '—':
            label = str(invoice._meta.get_field(field_name).verbose_name)
            result[label] = {'from': value, 'to': _('odstraněno')}
    return result


def _created_contact_values(contact):
    result = {}
    for field_name in ['role', 'phone', 'email', 'is_primary', 'note']:
        value = _audit_value(contact, field_name)
        if value == '—' or (field_name == 'is_primary' and value == _('Ne')):
            continue
        label = str(contact._meta.get_field(field_name).verbose_name)
        result[label] = {'from': '—', 'to': value}
    return result


def _record_contact_created(customer, contact, user):
    CustomerChange.objects.create(
        customer=customer,
        user=user,
        action=CustomerChange.Action.CONTACT_CREATED,
        subject=contact.name,
        changes=_created_contact_values(contact),
    )


def _job_contact_data(job):
    person = job.effective_contact
    return {
        'name': person.name if person else '—',
        'role': person.get_role_display() if person else '—',
        'phone': (person.phone if person else '') or job.customer.phone or '—',
        'email': (person.email if person else '') or job.customer.email or '—',
    }


def _format_date(value):
    from django.utils.formats import date_format
    return date_format(value, 'DATE_FORMAT') if value else '—'


def _format_price(value):
    from django.utils.formats import number_format
    return number_format(value, decimal_pos=2, use_l10n=True) + ' CZK'


@login_required
def dashboard(request):
    jobs = Job.objects.select_related('customer', 'contact', 'responsible').filter(is_archived=False)
    return render(request, 'records/dashboard.html', {
        'customers_count': Customer.objects.filter(status=Customer.Status.ACTIVE).count(),
        'open_jobs_count': jobs.exclude(status__in=[Job.Status.DONE, Job.Status.CANCELLED]).count(),
        'total_value': jobs.exclude(status=Job.Status.CANCELLED).aggregate(total=Sum('price'))['total'] or 0,
        'recent_jobs': jobs[:6],
        'showcase': Job.objects.filter(job_number='WB-2026-001').first(),
    })


@login_required
def customer_list(request):
    query = request.GET.get('q', '').strip()
    state = request.GET.get('state', Customer.Status.ACTIVE)
    sort = request.GET.get('sort', 'name')
    direction = request.GET.get('dir', 'asc')
    customers = Customer.objects.prefetch_related('contacts').annotate(jobs_total=Count('jobs'))
    if query:
        customers = customers.filter(Q(name__icontains=query) | Q(company_id__icontains=query) | Q(email__icontains=query) | Q(phone__icontains=query) | Q(contacts__name__icontains=query)).distinct()
    if state != 'all':
        customers = customers.filter(status=state)
    sort_map = {'name': 'name', 'created': 'created_at', 'city': 'city', 'jobs': 'jobs_total', 'status': 'status'}
    order = sort_map.get(sort, 'name')
    if direction == 'desc':
        order = f'-{order}'
    customers = customers.order_by(order)
    return render(request, 'records/customer_list.html', {'customers': customers, 'query': query, 'state': state, 'sort': sort, 'direction': direction, 'state_choices': Customer.Status.choices})


@login_required
def customer_detail(request, pk):
    customer = get_object_or_404(Customer.objects.prefetch_related('contacts', 'jobs__contact', 'history__user'), pk=pk)
    jobs = customer.jobs.all()
    return render(request, 'records/customer_detail.html', {
        'customer': customer,
        'open_jobs': jobs.filter(is_archived=False).exclude(status__in=[Job.Status.DONE, Job.Status.CANCELLED]),
        'completed_jobs': jobs.filter(is_archived=False, status=Job.Status.DONE),
        'history_jobs': jobs.filter(Q(is_archived=True) | Q(status=Job.Status.CANCELLED)),
        'show_customer_history': request.GET.get('history') == 'open',
    })


@roles_required(ROLE_ADMIN, ROLE_MANAGER)
@transaction.atomic
def customer_form(request, pk=None):
    customer = get_object_or_404(Customer, pk=pk) if pk else None
    before = Customer.objects.get(pk=pk) if pk else None
    form = CustomerForm(request.POST or None, instance=customer)
    if form.is_valid():
        saved_customer = form.save()
        if before:
            changes = _model_changes(before, saved_customer, TRACKED_CUSTOMER_FIELDS)
            if changes:
                CustomerChange.objects.create(customer=saved_customer, user=request.user, action=CustomerChange.Action.UPDATED, changes=changes)
        else:
            CustomerChange.objects.create(customer=saved_customer, user=request.user, action=CustomerChange.Action.CREATED)
        return redirect(saved_customer)
    return render(request, 'records/form.html', {'form': form, 'title': _('Upravit zákazníka') if customer else _('Nový zákazník'), 'customer_form': True})


def _ares_customer(subject):
    address = subject.get('sidlo') or {}
    street_name = address.get('nazevUlice') or address.get('nazevCastiObce') or ''
    house_number = str(address.get('cisloDomovni') or '')
    orientation_number = str(address.get('cisloOrientacni') or '')
    number = f'{house_number}/{orientation_number}' if orientation_number and house_number else house_number or orientation_number
    return {
        'name': subject.get('obchodniJmeno', ''),
        'company_id': subject.get('ico', ''),
        'street': ' '.join(part for part in [street_name, number] if part),
        'city': address.get('nazevObce', ''),
        'postal_code': str(address.get('psc') or ''),
        'full_address': address.get('textovaAdresa', ''),
    }


@roles_required(ROLE_ADMIN, ROLE_MANAGER)
def ares_search(request):
    query = request.GET.get('q', '').strip()
    if len(query) < 2:
        return JsonResponse({'error': _('Zadejte alespoň 2 znaky.')}, status=400)
    base = 'https://ares.gov.cz/ekonomicke-subjekty-v-be/rest/ekonomicke-subjekty'
    try:
        if query.isdigit() and len(query) == 8:
            req = Request(f'{base}/{quote(query)}', headers={'Accept': 'application/json', 'User-Agent': 'Zakazkovnik/1.0'})
            with urlopen(req, timeout=8) as response:
                subjects = [json.load(response)]
        else:
            payload = json.dumps({'obchodniJmeno': query, 'start': 0, 'pocet': 10}).encode('utf-8')
            req = Request(f'{base}/vyhledat', data=payload, headers={'Accept': 'application/json', 'Content-Type': 'application/json', 'User-Agent': 'Zakazkovnik/1.0'}, method='POST')
            with urlopen(req, timeout=8) as response:
                subjects = json.load(response).get('ekonomickeSubjekty', [])
    except HTTPError as exc:
        if exc.code == 404:
            return JsonResponse({'results': []})
        return JsonResponse({'error': _('ARES požadavek odmítl.')}, status=502)
    except (URLError, TimeoutError, json.JSONDecodeError):
        return JsonResponse({'error': _('ARES je momentálně nedostupný. Údaje lze vyplnit ručně.')}, status=502)
    return JsonResponse({'results': [_ares_customer(subject) for subject in subjects[:10]]})


@roles_required(ROLE_ADMIN)
@require_POST
def customer_delete(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    if customer.jobs.exists():
        messages.error(request, _('Zákazníka se zakázkami nelze trvale odstranit. Nejdříve ho archivujte.'))
        return redirect('customer-detail', pk=pk)
    customer.delete()
    return redirect('customer-list')


@roles_required(ROLE_ADMIN, ROLE_MANAGER)
@require_POST
@transaction.atomic
def customer_archive(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    old_status = customer.get_status_display()
    customer.status = Customer.Status.ACTIVE if customer.status == Customer.Status.ARCHIVED else Customer.Status.ARCHIVED
    customer.save(update_fields=['status'])
    CustomerChange.objects.create(
        customer=customer,
        user=request.user,
        action=CustomerChange.Action.RESTORED if customer.status == Customer.Status.ACTIVE else CustomerChange.Action.ARCHIVED,
        changes={_('Stav'): {'from': old_status, 'to': customer.get_status_display()}},
    )
    return redirect('customer-detail', pk=pk)


@login_required
@transaction.atomic
def contact_form(request, customer_pk, pk=None):
    customer = get_object_or_404(Customer, pk=customer_pk)
    contact = get_object_or_404(Contact, pk=pk, customer=customer) if pk else None
    if contact and not has_role(request.user, ROLE_ADMIN, ROLE_MANAGER):
        raise PermissionDenied(_('Uložené kontakty mohou upravovat pouze správci a administrátoři.'))
    before = Contact.objects.get(pk=pk) if pk else None
    form = ContactForm(request.POST or None, instance=contact)
    if form.is_valid():
        previous_primary = None
        if form.cleaned_data.get('is_primary'):
            previous_primary = customer.contacts.filter(is_primary=True).exclude(pk=pk).first()
        item = form.save(commit=False)
        item.customer = customer
        item.save()
        if before:
            changes = _model_changes(before, item, TRACKED_CONTACT_FIELDS)
            if changes:
                CustomerChange.objects.create(customer=customer, user=request.user, action=CustomerChange.Action.CONTACT_UPDATED, subject=item.name, changes=changes)
        else:
            _record_contact_created(customer, item, request.user)
        if previous_primary:
            CustomerChange.objects.create(
                customer=customer,
                user=request.user,
                action=CustomerChange.Action.CONTACT_UPDATED,
                subject=previous_primary.name,
                changes={_('Hlavní kontakt'): {'from': _('Ano'), 'to': _('Ne')}},
            )
        return redirect('customer-detail', pk=customer.pk)
    return render(request, 'records/form.html', {'form': form, 'title': 'Upravit kontakt' if contact else _('Nový kontakt'), 'cancel_url': customer.get_absolute_url()})


@roles_required(ROLE_ADMIN)
@require_POST
@transaction.atomic
def contact_delete(request, customer_pk, pk):
    contact = get_object_or_404(Contact, pk=pk, customer_id=customer_pk)
    customer = contact.customer
    subject = contact.name
    changes = _deleted_contact_values(contact)
    contact.delete()
    CustomerChange.objects.create(customer=customer, user=request.user, action=CustomerChange.Action.CONTACT_DELETED, subject=subject, changes=changes)
    return redirect('customer-detail', pk=customer_pk)


@login_required
def job_list(request):
    query = request.GET.get('q', '').strip()
    view = request.GET.get('view', 'open')
    sort = request.GET.get('sort', 'due')
    direction = request.GET.get('dir', 'asc')
    jobs = Job.objects.select_related('customer', 'contact', 'responsible')
    if query:
        translated_ids = [pk for pk,title in jobs.values_list('pk','title') if query.casefold() in _(title).casefold()]
        jobs = jobs.filter(Q(pk__in=translated_ids) | Q(job_number__icontains=query) | Q(title__icontains=query) | Q(customer__name__icontains=query) | Q(contact__name__icontains=query) | Q(contact__email__icontains=query) | Q(contact__phone__icontains=query))
    if view == 'open':
        jobs = jobs.filter(is_archived=False).exclude(status__in=[Job.Status.DONE, Job.Status.CANCELLED])
    elif view == 'done':
        jobs = jobs.filter(is_archived=False, status=Job.Status.DONE)
    elif view == 'cancelled':
        jobs = jobs.filter(is_archived=False, status=Job.Status.CANCELLED)
    elif view == 'archived':
        jobs = jobs.filter(is_archived=True)
    status_order = Case(When(status=Job.Status.IN_PROGRESS, then=1), When(status=Job.Status.NEW, then=2), When(status=Job.Status.WAITING, then=3), When(status=Job.Status.DONE, then=4), When(status=Job.Status.CANCELLED, then=5), default=6, output_field=IntegerField())
    jobs = jobs.annotate(status_order=status_order)
    sort_map = {'number': 'job_number', 'title': 'title', 'customer': 'customer__name', 'status': 'status_order', 'created': 'created_at', 'due': 'due_date', 'completed': 'completed_at', 'price': 'price'}
    order = sort_map.get(sort, 'due_date')
    if direction == 'desc':
        order = f'-{order}'
    jobs = jobs.order_by(order, 'job_number')
    return render(request, 'records/job_list.html', {'jobs': jobs, 'query': query, 'view': view, 'sort': sort, 'direction': direction})


@login_required
def job_detail(request, pk):
    job = get_object_or_404(Job.objects.select_related('customer', 'contact', 'responsible').prefetch_related('customer__contacts'), pk=pk)
    invoices = list(Invoice.objects.filter(job=job).select_related('created_by', 'updated_by'))
    return render(request, 'records/job_detail.html', {
        'job': job,
        'invoices': invoices,
    })


def _check_invoice_edit_permission(request, job):
    if get_user_role(request.user) == ROLE_MEMBER and (job.is_archived or job.status == Job.Status.CANCELLED):
        raise PermissionDenied(_('Člen nemůže měnit fakturu u archivované nebo zrušené zakázky.'))


@login_required
def invoice_detail(request, job_pk, invoice_pk):
    job = get_object_or_404(Job.objects.select_related('customer'), pk=job_pk)
    invoice = get_object_or_404(
        Invoice.objects.select_related('created_by', 'updated_by'),
        pk=invoice_pk,
        job=job,
    )
    can_edit_invoice = get_user_role(request.user) != ROLE_MEMBER or (
        not job.is_archived and job.status != Job.Status.CANCELLED
    )
    return render(request, 'records/invoice_detail.html', {
        'job': job,
        'invoice': invoice,
        'can_edit_invoice': can_edit_invoice,
    })


@login_required
def invoice_scan(request, job_pk):
    job = get_object_or_404(Job, pk=job_pk)
    _check_invoice_edit_permission(request, job)
    form = InvoiceUploadForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        try:
            if form.cleaned_data['ocr_text']:
                initial = parse_invoice_text(form.cleaned_data['ocr_text'])
            else:
                initial = extract_invoice_data(form.cleaned_data['document'])
        except InvoiceScanError as exc:
            form.add_error('document', str(exc))
        except Exception:
            form.add_error('document', _('OCR se nepodařilo dokončit. Zkuste menší nebo ostřejší snímek.'))
        else:
            review_form = InvoiceForm(initial=initial)
            return render(request, 'records/invoice_form.html', {
                'job': job,
                'form': review_form,
                'is_ocr_review': True,
            })
    return render(request, 'records/invoice_scan.html', {'job': job, 'form': form})


@login_required
@transaction.atomic
def invoice_form(request, job_pk, invoice_pk=None):
    job = get_object_or_404(Job, pk=job_pk)
    _check_invoice_edit_permission(request, job)
    invoice = get_object_or_404(Invoice, pk=invoice_pk, job=job) if invoice_pk else None
    if request.method != 'POST' and not invoice:
        return redirect('invoice-scan', job_pk=job.pk)
    before = Invoice.objects.get(pk=invoice.pk) if invoice else None
    form = InvoiceForm(request.POST or None, instance=invoice)
    if request.method == 'POST' and form.is_valid():
        saved_invoice = form.save(commit=False)
        saved_invoice.job = job
        saved_invoice.updated_by = request.user
        if not invoice:
            saved_invoice.created_by = request.user
        saved_invoice.save()
        if before:
            changes = _model_changes(before, saved_invoice, TRACKED_INVOICE_FIELDS)
            if changes:
                JobChange.objects.create(job=job, user=request.user, action=JobChange.Action.INVOICE_UPDATED, changes=changes)
            messages.success(request, _('Údaje faktury byly upraveny.'))
        else:
            changes = _model_changes(Invoice(job=job), saved_invoice, TRACKED_INVOICE_FIELDS)
            JobChange.objects.create(job=job, user=request.user, action=JobChange.Action.INVOICE_CREATED, changes=changes)
            messages.success(request, _('Faktura byla uložena. Původní snímek se neukládá.'))
        return redirect('invoice-detail', job_pk=job.pk, invoice_pk=saved_invoice.pk)
    return render(request, 'records/invoice_form.html', {'job': job, 'form': form, 'invoice': invoice})


@roles_required(ROLE_ADMIN)
@require_POST
@transaction.atomic
def invoice_delete(request, job_pk, invoice_pk):
    job = get_object_or_404(Job, pk=job_pk)
    invoice = get_object_or_404(Invoice, pk=invoice_pk, job=job)
    changes = _deleted_invoice_values(invoice)
    invoice_number = invoice.invoice_number or _('bez čísla')
    invoice.delete()
    JobChange.objects.create(
        job=job,
        user=request.user,
        action=JobChange.Action.INVOICE_DELETED,
        changes=changes,
    )
    messages.success(request, f'Faktura {invoice_number} byla trvale odstraněna.')
    return redirect('job-detail', pk=job.pk)


@login_required
@transaction.atomic
def job_form(request, pk=None):
    job = get_object_or_404(Job, pk=pk) if pk else None
    role = get_user_role(request.user)
    if job and role == ROLE_MEMBER and (job.is_archived or job.status == Job.Status.CANCELLED):
        raise PermissionDenied(_('Člen nemůže upravovat archivovanou nebo zrušenou zakázku.'))
    before = Job.objects.select_related('customer', 'contact', 'responsible').get(pk=pk) if pk else None
    initial = {}
    if not job and request.GET.get('customer'):
        initial['customer'] = request.GET['customer']
    form = JobForm(request.POST or None, instance=job, initial=initial, role=role)
    if form.is_valid():
        saved_job = form.save(commit=False)
        new_contact = None
        if form.cleaned_data.get('new_contact_name'):
            new_contact = Contact.objects.create(
                customer=saved_job.customer,
                name=form.cleaned_data['new_contact_name'],
                role=form.cleaned_data.get('new_contact_role') or Contact.Role.OTHER,
                phone=form.cleaned_data.get('new_contact_phone', ''),
                email=form.cleaned_data.get('new_contact_email', ''),
                is_primary=not saved_job.customer.contacts.exists(),
            )
            saved_job.contact = new_contact
            _record_contact_created(saved_job.customer, new_contact, request.user)
        saved_job.save()
        if before:
            changes = _job_changes(before, saved_job)
            if changes:
                JobChange.objects.create(job=saved_job, user=request.user, action=JobChange.Action.UPDATED, changes=changes, reason=form.cleaned_data.get('change_reason', ''))
        else:
            changes = {}
            if saved_job.contact:
                changes[_('Kontakt pro zakázku')] = {'from': '—', 'to': str(saved_job.contact)}
            JobChange.objects.create(job=saved_job, user=request.user, action=JobChange.Action.CREATED, changes=changes)
        return redirect(saved_job)
    return render(request, 'records/form.html', {'form': form, 'title': _('Upravit zakázku') if job else _('Nová zakázka'), 'job': job, 'job_form': True})


@roles_required(ROLE_ADMIN, ROLE_MANAGER)
@transaction.atomic
def job_transfer(request, pk):
    job = get_object_or_404(Job, pk=pk)
    before = Job.objects.select_related('customer', 'contact', 'responsible').get(pk=pk)
    form = JobTransferForm(request.POST or None, instance=job)
    if form.is_valid() and request.method == 'POST':
        saved_job = form.save()
        changes = _job_changes(before, saved_job, ['customer', 'contact'])
        JobChange.objects.create(job=saved_job, user=request.user, action=JobChange.Action.TRANSFERRED, changes=changes, reason=form.cleaned_data.get('change_reason', ''))
        messages.success(request, _('Zakázka byla přeřazena k vybranému zákazníkovi.'))
        return redirect('job-detail', pk=pk)
    return render(request, 'records/transfer.html', {'form': form, 'job': job})


@roles_required(ROLE_ADMIN)
@require_POST
def job_delete(request, pk):
    job = get_object_or_404(Job, pk=pk)
    if job.status == Job.Status.DONE:
        messages.error(request, _('Dokončenou zakázku nelze trvale odstranit. Lze ji archivovat.'))
        return redirect('job-detail', pk=pk)
    job.delete()
    return redirect('job-list')


@roles_required(ROLE_ADMIN, ROLE_MANAGER)
@require_POST
def job_archive(request, pk):
    job = get_object_or_404(Job, pk=pk)
    job.is_archived = not job.is_archived
    job.save(update_fields=['is_archived'])
    JobChange.objects.create(job=job, user=request.user, action=JobChange.Action.ARCHIVED if job.is_archived else JobChange.Action.RESTORED)
    return redirect('job-detail', pk=pk)


@roles_required(ROLE_ADMIN, ROLE_MANAGER)
def jobs_csv(request):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="zakazky.csv"'
    response.write('\ufeff')
    writer = csv.writer(response, delimiter=';')
    def safe_cell(value):
        if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@', '\t', '\r', '\n')):
            return "'" + value
        return value
    writer.writerow([_('Číslo'), _('Zakázka'), _('Zákazník'), _('Kontakt'), _('Telefon'), _('E-mail'), _('Stav'), _('Založeno'), _('Termín'), _('Dokončeno'), _('Cena')])
    for job in Job.objects.select_related('customer', 'contact', 'responsible').prefetch_related('customer__contacts'):
        contact = job.effective_contact
        phone = (contact.phone if contact else '') or job.customer.phone
        email = (contact.email if contact else '') or job.customer.email
        writer.writerow([safe_cell(value) for value in [job.job_number, _(job.title), job.customer.name, contact.name if contact else '', phone, email, job.get_status_display(), job.created_at.date(), job.due_date or '', job.completed_at or '', job.price]])
    return response


@roles_required(ROLE_ADMIN)
def user_list(request):
    accounts = get_user_model().objects.prefetch_related('groups').order_by('username')
    rows = [{'account': account, 'role_label': get_role_label(account)} for account in accounts]
    return render(request, 'records/user_list.html', {'rows': rows})


@roles_required(ROLE_ADMIN)
@transaction.atomic
def user_create(request):
    form = AppUserCreationForm(request.POST or None)
    if form.is_valid():
        account = form.save()
        messages.success(request, f'Uživatel {account.username} byl vytvořen.')
        return redirect('user-list')
    return render(request, 'records/form.html', {
        'form': form,
        'title': _('Nový uživatel'),
        'cancel_url': reverse('user-list'),
    })


@roles_required(ROLE_ADMIN)
@transaction.atomic
def user_update(request, pk):
    account = get_object_or_404(get_user_model(), pk=pk)
    form = AppUserUpdateForm(request.POST or None, instance=account)
    if form.is_valid():
        if account == request.user and form.cleaned_data['role'] != ROLE_ADMIN:
            form.add_error('role', _('Vlastnímu účtu nemůžete odebrat roli administrátora.'))
        if account == request.user and not form.cleaned_data['is_active']:
            form.add_error('is_active', _('Vlastní účet nemůžete deaktivovat.'))
        if not form.errors:
            password_changed = bool(form.cleaned_data.get('new_password1'))
            account = form.save()
            if account == request.user and password_changed:
                update_session_auth_hash(request, account)
            messages.success(request, f'Uživatel {account.username} byl upraven.')
            return redirect('user-list')
    return render(request, 'records/form.html', {
        'form': form,
        'title': f'Upravit uživatele {account.username}',
        'cancel_url': reverse('user-list'),
    })


@login_required
def job_pdf(request, pk):
    job = get_object_or_404(Job.objects.select_related('customer', 'contact', 'responsible').prefetch_related('customer__contacts'), pk=pk)
    buffer = BytesIO()
    font_path = Path(__file__).resolve().parent.parent / 'static' / 'fonts' / 'DejaVuSans.ttf'
    pdfmetrics.registerFont(TTFont('DejaVu', font_path))
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=22 * mm,
        leftMargin=22 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title=job.job_number or f'Zakázka {job.pk}',
    )
    normal = ParagraphStyle('NormalCZ', fontName='DejaVu', fontSize=10.5, leading=15, textColor=colors.HexColor('#17211d'))
    meta = ParagraphStyle('MetaCZ', parent=normal, fontSize=10, leading=13, textColor=colors.HexColor('#147653'), spaceAfter=5)
    title = ParagraphStyle('TitleCZ', parent=normal, fontSize=22, leading=27, spaceAfter=16)
    section = ParagraphStyle('SectionCZ', parent=normal, fontSize=13, leading=18, textColor=colors.HexColor('#147653'), spaceBefore=12, spaceAfter=8)
    label = ParagraphStyle('LabelCZ', parent=normal, fontSize=9.5, textColor=colors.HexColor('#68756f'))

    def paragraph(value, style=normal):
        return Paragraph(escape(str(value)).replace('\n', '<br/>'), style)

    contact = _job_contact_data(job)
    job_rows = [
        (_('Zákazník'), job.customer.name),
        (_('Odpovědná osoba'), job.responsible.get_full_name() if job.responsible else '—'),
        (_('Stav'), job.get_status_display()),
        (_('Založeno'), _format_date(job.created_at.date())),
        (_('Termín'), _format_date(job.due_date)),
        (_('Dokončeno'), _format_date(job.completed_at)),
        (_('Cena'), _format_price(job.price)),
    ]
    contact_rows = [
        (_('Jméno'), contact['name']),
        (_('Funkce'), contact['role']),
        (_('Telefon'), contact['phone']),
        (_('E-mail'), contact['email']),
    ]

    def detail_table(rows):
        table = Table([[paragraph(key, label), paragraph(value)] for key, value in rows], colWidths=[38 * mm, 115 * mm], hAlign='LEFT')
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f4f7f5')),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#d7e0db')),
            ('INNERGRID', (0, 0), (-1, -1), 0.35, colors.HexColor('#e1e7e4')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 9),
            ('RIGHTPADDING', (0, 0), (-1, -1), 9),
            ('TOPPADDING', (0, 0), (-1, -1), 7),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ]))
        return table

    story = [
        paragraph(job.job_number or f'Zakázka #{job.pk}', meta),
        paragraph(_(job.title), title),
        paragraph(_('Zakázka'), section),
        detail_table(job_rows),
        paragraph(_('Kontakt pro zakázku'), section),
        detail_table(contact_rows),
        paragraph(_('Popis'), section),
        paragraph(_(job.description) or 'Bez popisu.'),
        Spacer(1, 6 * mm),
    ]
    document.build(story)
    buffer.seek(0)
    return FileResponse(buffer, as_attachment=True, filename=f'zakazka-{job.pk}.pdf')
