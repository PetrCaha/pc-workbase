from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone


class Customer(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'active', _('Aktivní')
        INACTIVE = 'inactive', _('Neaktivní')
        ARCHIVED = 'archived', _('Archivovaný')

    name = models.CharField(_('Jméno / název firmy'), max_length=160)
    company_id = models.CharField(_('IČO'), max_length=8, blank=True, unique=True, null=True)
    email = models.EmailField(_('E-mail'), blank=True)
    phone = models.CharField(_('Telefon'), max_length=30, blank=True)
    street = models.CharField(_('Ulice a číslo'), max_length=160, blank=True)
    city = models.CharField(_('Město'), max_length=100, blank=True)
    postal_code = models.CharField(_('PSČ'), max_length=10, blank=True)
    note = models.TextField(_('Poznámka'), blank=True)
    status = models.CharField(_('Stav'), max_length=12, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(_('Vytvořeno'), auto_now_add=True)
    updated_at = models.DateTimeField('Upraveno', auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = _('zákazník')
        verbose_name_plural = _('zákazníci')

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('customer-detail', args=[self.pk])

    @property
    def main_contact(self):
        contacts = list(self.contacts.all())
        return next((contact for contact in contacts if contact.is_primary), contacts[0] if contacts else None)


class Contact(models.Model):
    class Role(models.TextChoices):
        EXECUTIVE = 'executive', _('Jednatel')
        ORDERING = 'ordering', _('Objednatel')
        TECHNICAL = 'technical', _('Technický kontakt')
        BILLING = 'billing', _('Fakturace')
        OTHER = 'other', _('Jiná')

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='contacts', verbose_name=_('Zákazník'))
    name = models.CharField(_('Jméno a příjmení'), max_length=160)
    role = models.CharField(_('Funkce'), max_length=20, choices=Role.choices, default=Role.OTHER)
    phone = models.CharField(_('Telefon'), max_length=30, blank=True)
    email = models.EmailField(_('E-mail'), blank=True)
    note = models.TextField(_('Poznámka'), blank=True)
    is_primary = models.BooleanField(_('Hlavní kontakt'), default=False)

    class Meta:
        ordering = ['-is_primary', 'name']
        verbose_name = _('kontaktní osoba')
        verbose_name_plural = _('kontaktní osoby')

    def __str__(self):
        return f'{self.name} – {self.get_role_display()}'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_primary:
            Contact.objects.filter(customer=self.customer, is_primary=True).exclude(pk=self.pk).update(is_primary=False)


class CustomerChange(models.Model):
    class Action(models.TextChoices):
        CREATED = 'created', _('Založení zákazníka')
        UPDATED = 'updated', _('Úprava zákazníka')
        CONTACT_CREATED = 'contact_created', _('Přidání kontaktu')
        CONTACT_UPDATED = 'contact_updated', _('Úprava kontaktu')
        CONTACT_DELETED = 'contact_deleted', _('Odstranění kontaktu')
        ARCHIVED = 'archived', _('Archivace zákazníka')
        RESTORED = 'restored', _('Obnovení zákazníka')

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='history', verbose_name=_('Zákazník'))
    user = models.ForeignKey('auth.User', on_delete=models.SET_NULL, blank=True, null=True, verbose_name=_('Uživatel'))
    action = models.CharField('Akce', max_length=24, choices=Action.choices)
    subject = models.CharField(_('Položka'), max_length=160, blank=True)
    changes = models.JSONField(_('Změny'), default=dict, blank=True)
    created_at = models.DateTimeField('Provedeno', auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('změna zákazníka')
        verbose_name_plural = _('historie zákazníků')

    def __str__(self):
        return f'{self.customer} – {self.get_action_display()}'


class Job(models.Model):
    class Status(models.TextChoices):
        NEW = 'new', _('Nová')
        IN_PROGRESS = 'in_progress', _('Probíhá')
        WAITING = 'waiting', _('Čeká')
        DONE = 'done', _('Dokončena')
        CANCELLED = 'cancelled', _('Zrušena')

    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='jobs', verbose_name=_('Zákazník'))
    responsible = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_jobs', verbose_name=_('Odpovědná osoba'))
    contact = models.ForeignKey(Contact, on_delete=models.SET_NULL, related_name='jobs', verbose_name=_('Kontakt pro zakázku'), blank=True, null=True)
    job_number = models.CharField(_('Číslo zakázky'), max_length=20, unique=True, blank=True, null=True)
    title = models.CharField(_('Název zakázky'), max_length=180)
    description = models.TextField(_('Popis'), blank=True)
    status = models.CharField(_('Stav'), max_length=20, choices=Status.choices, default=Status.NEW)
    due_date = models.DateField(_('Termín'), blank=True, null=True)
    completed_at = models.DateField(_('Dokončeno'), blank=True, null=True)
    cancellation_reason = models.TextField(_('Důvod zrušení'), blank=True)
    is_archived = models.BooleanField(_('Archivováno'), default=False)
    price = models.DecimalField(_('Cena'), max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    created_at = models.DateTimeField(_('Vytvořeno'), auto_now_add=True)
    updated_at = models.DateTimeField('Upraveno', auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('zakázka')
        verbose_name_plural = _('zakázky')

    def __str__(self):
        return str(_(self.title))

    def get_absolute_url(self):
        return reverse('job-detail', args=[self.pk])

    @property
    def effective_contact(self):
        return self.contact or self.customer.main_contact

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.contact_id and self.contact.customer_id != self.customer_id:
            raise ValidationError({'contact': _('Vybraný kontakt nepatří tomuto zákazníkovi.')})

    def save(self, *args, **kwargs):
        if self.status == self.Status.DONE and not self.completed_at:
            self.completed_at = timezone.localdate()
        elif self.status != self.Status.DONE:
            self.completed_at = None
        super().save(*args, **kwargs)
        if not self.job_number:
            self.job_number = f'Z-{self.created_at.year}-{self.pk:04d}'
            super().save(update_fields=['job_number'])


class JobChange(models.Model):
    class Action(models.TextChoices):
        CREATED = 'created', _('Založení')
        UPDATED = 'updated', _('Úprava')
        TRANSFERRED = 'transferred', _('Změna zákazníka')
        ARCHIVED = 'archived', _('Archivace')
        RESTORED = 'restored', _('Obnovení')
        INVOICE_CREATED = 'invoice_created', _('Přidání faktury')
        INVOICE_UPDATED = 'invoice_updated', _('Úprava faktury')
        INVOICE_DELETED = 'invoice_deleted', _('Odstranění faktury')

    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='history', verbose_name=_('Zakázka'))
    user = models.ForeignKey('auth.User', on_delete=models.SET_NULL, blank=True, null=True, verbose_name=_('Uživatel'))
    action = models.CharField('Akce', max_length=20, choices=Action.choices)
    changes = models.JSONField(_('Změny'), default=dict, blank=True)
    reason = models.TextField(_('Důvod změny'), blank=True)
    created_at = models.DateTimeField('Provedeno', auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('změna zakázky')
        verbose_name_plural = _('historie zakázek')


class Invoice(models.Model):
    paid_on = models.DateField(_('Datum úhrady'), blank=True, null=True)

    @property
    def payment_status(self):
        from django.conf import settings
        from datetime import date
        if self.paid_on:
            return 'paid'
        reference = date.fromisoformat(settings.DEMO_REFERENCE_DATE)
        return 'overdue' if self.due_date and self.due_date < reference else 'pending'

    def get_payment_status_display(self):
        from django.utils.translation import gettext as _
        return {'paid': _('Uhrazena'), 'pending': _('Čeká na úhradu'), 'overdue': _('Po splatnosti')}[self.payment_status]
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='invoices', verbose_name=_('Zakázka'))
    supplier_name = models.CharField(_('Dodavatel'), max_length=200, blank=True)
    supplier_company_id = models.CharField(_('IČO dodavatele'), max_length=12, blank=True)
    supplier_address = models.TextField('Adresa dodavatele', blank=True)
    customer_header = models.TextField(_('Odběratel / hlavička'), blank=True)
    invoice_number = models.CharField(_('Číslo faktury'), max_length=80, blank=True)
    variable_symbol = models.CharField(_('Variabilní symbol'), max_length=40, blank=True)
    issue_date = models.DateField(_('Datum vystavení'), blank=True, null=True)
    taxable_date = models.DateField(_('Datum zdanitelného plnění'), blank=True, null=True)
    due_date = models.DateField('Datum splatnosti', blank=True, null=True)
    payment_method = models.CharField(_('Způsob platby'), max_length=100, blank=True)
    items_text = models.TextField(_('Práce a materiál'), blank=True)
    subtotal = models.DecimalField(_('Základ daně'), max_digits=14, decimal_places=2, blank=True, null=True)
    vat_amount = models.DecimalField(_('DPH'), max_digits=14, decimal_places=2, blank=True, null=True)
    total_amount = models.DecimalField(_('Celkem k úhradě'), max_digits=14, decimal_places=2, blank=True, null=True)
    currency = models.CharField(_('Měna'), max_length=8, default='CZK')
    note = models.TextField(_('Poznámka'), blank=True)
    raw_text = models.TextField(_('Původní rozpoznaný text'), blank=True)
    created_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, blank=True, null=True, related_name='created_invoices', verbose_name=_('Vytvořil'))
    updated_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, blank=True, null=True, related_name='updated_invoices', verbose_name='Naposledy upravil')
    created_at = models.DateTimeField(_('Vytvořeno'), auto_now_add=True)
    updated_at = models.DateTimeField('Upraveno', auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'faktura'
        verbose_name_plural = 'faktury'

    def __str__(self):
        return self.invoice_number or f'Faktura k {self.job}'

# Create your models here.
