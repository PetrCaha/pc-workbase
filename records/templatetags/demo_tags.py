from django import template
from django.utils.translation import gettext as _
register = template.Library()
@register.filter
def demo_text(value):
    return _(str(value)) if value else value
@register.filter
def sort_options(kind):
    options = {
        'customers': [('name', 'Název'), ('city', 'Město'), ('jobs', 'Počet zakázek'), ('created', 'Založeno'), ('status', 'Stav')],
        'jobs': [('due', 'Termín'), ('number', 'Číslo'), ('title', 'Název'), ('customer', 'Zákazník'), ('status', 'Stav'), ('price', 'Cena'), ('completed', 'Dokončeno'), ('created', 'Založeno')],
        'views': [('open', 'Otevřené'), ('done', 'Dokončené'), ('cancelled', 'Zrušené'), ('archived', 'Archivované'), ('all', 'Všechny')],
    }
    return [(key, _(label)) for key, label in options.get(kind, [])]

@register.filter
def history_label(value):
    return _({'status': 'Stav', 'price': 'Cena', 'responsible': 'Odpovědná osoba', 'invoice_number': 'Číslo faktury', 'due_date': 'Termín'}.get(value, value))
