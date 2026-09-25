from django.utils.translation import gettext_lazy as _
import re

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import Contact, Customer, Invoice, Job
from .permissions import ROLE_CHOICES, ROLE_MEMBER, get_user_role, set_user_role


class DateInput(forms.DateInput):
    input_type = 'date'

    def __init__(self, attrs=None, format=None):
        super().__init__(attrs=attrs, format=format or '%Y-%m-%d')


class InvoiceUploadForm(forms.Form):
    document = forms.FileField(label='Fotografie nebo PDF faktury', required=False)
    ocr_text = forms.CharField(required=False, max_length=100_000, widget=forms.HiddenInput())

    def clean_document(self):
        document = self.cleaned_data.get('document')
        if not document:
            return None
        if document.size > 10 * 1024 * 1024:
            raise forms.ValidationError(_('Soubor je větší než 10 MB. Vyfoťte fakturu v nižším rozlišení.'))
        allowed_types = {'image/jpeg', 'image/png', 'image/webp', 'application/pdf'}
        if document.content_type not in allowed_types:
            raise forms.ValidationError(_('Použijte obrázek JPG, PNG, WebP nebo PDF.'))
        return document

    def clean(self):
        cleaned_data = super().clean()
        document = cleaned_data.get('document')
        ocr_text = (cleaned_data.get('ocr_text') or '').strip()
        if ocr_text and len(re.sub(r'\s+', '', ocr_text)) < 20:
            self.add_error('ocr_text', _('Na snímku se nepodařilo najít dostatek textu. Vyfoťte fakturu znovu zblízka.'))
        elif not document and not ocr_text:
            self.add_error('document', _('Vyfoťte fakturu nebo vyberte PDF.'))
        elif document and document.content_type != 'application/pdf' and not ocr_text:
            self.add_error('document', _('Fotografii se nepodařilo přečíst v telefonu. Zkuste stránku obnovit a snímek pořídit znovu.'))
        cleaned_data['ocr_text'] = ocr_text
        return cleaned_data


class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = [
            'supplier_name', 'supplier_company_id', 'supplier_address', 'customer_header',
            'invoice_number', 'variable_symbol', 'issue_date', 'taxable_date', 'due_date',
            'payment_method', 'items_text', 'subtotal', 'vat_amount', 'total_amount',
            'currency', 'note', 'paid_on',
        ]
        widgets = {
            'paid_on': DateInput(),
            'issue_date': DateInput(),
            'taxable_date': DateInput(),
            'due_date': DateInput(),
            'supplier_address': forms.Textarea(attrs={'rows': 3}),
            'customer_header': forms.Textarea(attrs={'rows': 4}),
            'items_text': forms.Textarea(attrs={'rows': 8}),
            'note': forms.Textarea(attrs={'rows': 3}),
            'raw_text': forms.Textarea(attrs={'rows': 12, 'spellcheck': 'false'}),
        }

    def clean_supplier_company_id(self):
        value = ''.join(character for character in self.cleaned_data.get('supplier_company_id', '') if character.isdigit())
        if value and len(value) not in (8, 10, 12):
            raise forms.ValidationError(_('Zkontrolujte IČO dodavatele; rozpoznaná hodnota nevypadá platně.'))
        return value


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ['name', 'company_id', 'email', 'phone', 'street', 'city', 'postal_code', 'status', 'note']

    def clean_company_id(self):
        value = self.cleaned_data.get('company_id') or None
        if value and (not value.isdigit() or len(value) != 8):
            raise forms.ValidationError(_('IČO musí obsahovat přesně 8 číslic.'))
        return value


class JobForm(forms.ModelForm):
    change_reason = forms.CharField(label=_('Důvod změny'), required=False, widget=forms.Textarea(attrs={'rows': 2}), help_text=_('Volitelné. Uloží se do historie této úpravy.'))
    new_contact_name = forms.CharField(
        label=_('Jméno a příjmení'),
        required=False,
        max_length=160,
        help_text=_('Po uložení bude kontakt dostupný také u dalších zakázek tohoto zákazníka.'),
    )
    new_contact_role = forms.ChoiceField(label=_('Funkce'), required=False, choices=Contact.Role.choices, initial=Contact.Role.OTHER)
    new_contact_phone = forms.CharField(label=_('Telefon'), required=False, max_length=30)
    new_contact_email = forms.EmailField(label=_('E-mail'), required=False)

    class Meta:
        model = Job
        fields = ['customer', 'contact', 'responsible', 'title', 'description', 'status', 'due_date', 'completed_at', 'price']
        widgets = {'due_date': DateInput(), 'completed_at': DateInput()}

    def __init__(self, *args, role=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.role = role
        self.fields['responsible'].queryset = get_user_model().objects.filter(is_active=True, is_staff=False, is_superuser=False)
        self.fields['responsible'].label_from_instance = lambda user: user.get_full_name() or user.username
        customer_id = self.data.get('customer') or self.initial.get('customer') or getattr(self.instance, 'customer_id', None)
        self.fields['contact'].queryset = Contact.objects.filter(customer_id=customer_id) if str(customer_id).isdigit() else Contact.objects.none()
        self.fields['contact'].label = _('Uložený kontakt pro zakázku')
        self.fields['contact'].help_text = _('Vyberte uložený kontakt, nebo níže založte nový. Nevyplňujte obě možnosti současně.')
        if self.instance.pk:
            self.fields['customer'].disabled = True
            if role == ROLE_MEMBER:
                self.fields['title'].disabled = True
        else:
            self.fields.pop('change_reason')
        if role == ROLE_MEMBER:
            self.fields['status'].choices = [choice for choice in Job.Status.choices if choice[0] != Job.Status.CANCELLED]

    def clean(self):
        cleaned_data = super().clean()
        name = (cleaned_data.get('new_contact_name') or '').strip()
        role = cleaned_data.get('new_contact_role') or Contact.Role.OTHER
        phone = (cleaned_data.get('new_contact_phone') or '').strip()
        email = (cleaned_data.get('new_contact_email') or '').strip()
        selected_contact = cleaned_data.get('contact')

        cleaned_data['new_contact_name'] = name
        cleaned_data['new_contact_role'] = role
        cleaned_data['new_contact_phone'] = phone
        cleaned_data['new_contact_email'] = email

        if selected_contact and name:
            self.add_error('new_contact_name', _('Vyberte buď uložený kontakt, nebo zadejte nový kontakt ručně.'))
        if not name and (phone or email):
            self.add_error('new_contact_name', _('Pro uložení nového kontaktu doplňte jméno a příjmení.'))
        customer = cleaned_data.get('customer')
        if name and customer and not selected_contact:
            duplicates = customer.contacts.filter(name__iexact=name)
            if email:
                duplicates = duplicates.filter(email__iexact=email)
            elif phone:
                duplicates = duplicates.filter(phone=phone)
            if duplicates.exists():
                self.add_error('new_contact_name', _('Takový kontakt už je u zákazníka uložený. Vyberte ho z nabídky.'))
        return cleaned_data


class ContactForm(forms.ModelForm):
    class Meta:
        model = Contact
        fields = ['name', 'role', 'phone', 'email', 'is_primary', 'note']


class JobTransferForm(forms.ModelForm):
    change_reason = forms.CharField(label=_('Důvod změny'), required=False, widget=forms.Textarea(attrs={'rows': 2}))

    class Meta:
        model = Job
        fields = ['customer', 'contact']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        customer_id = self.data.get('customer') or getattr(self.instance, 'customer_id', None)
        self.fields['contact'].queryset = Contact.objects.filter(customer_id=customer_id) if str(customer_id).isdigit() else Contact.objects.none()


class AppUserCreationForm(UserCreationForm):
    role = forms.ChoiceField(label=_('Role'), choices=ROLE_CHOICES)

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ('username', 'first_name', 'last_name', 'email', 'role')

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            set_user_role(user, self.cleaned_data['role'])
        return user


class AppUserUpdateForm(forms.ModelForm):
    role = forms.ChoiceField(label=_('Role'), choices=ROLE_CHOICES)
    new_password1 = forms.CharField(
        label=_('Nové heslo'),
        required=False,
        strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        help_text=_('Nechte prázdné, pokud heslo nechcete měnit.'),
    )
    new_password2 = forms.CharField(
        label=_('Nové heslo znovu'),
        required=False,
        strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
    )

    class Meta:
        model = get_user_model()
        fields = ('username', 'first_name', 'last_name', 'email', 'is_active', 'role')
        labels = {'is_active': _('Aktivní účet')}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['role'].initial = get_user_role(self.instance)

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('new_password1')
        password2 = cleaned_data.get('new_password2')
        if password1 or password2:
            if password1 != password2:
                self.add_error('new_password2', _('Zadaná hesla se neshodují.'))
            elif password1:
                try:
                    validate_password(password1, user=self.instance)
                except ValidationError as error:
                    self.add_error('new_password1', error)
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            set_user_role(user, self.cleaned_data['role'])
            if self.cleaned_data.get('new_password1'):
                user.set_password(self.cleaned_data['new_password1'])
                user.save(update_fields=['password'])
        return user
