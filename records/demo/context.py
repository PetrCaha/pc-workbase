from django.conf import settings
from datetime import date
from django.utils.translation import gettext as _
def workspace(request):
    return {'demo_mode': True, 'reference_date': date.fromisoformat(settings.DEMO_REFERENCE_DATE), 'demo_message': _('Změny se v ukázce neukládají. Formulář si můžete vyzkoušet, původní ukázková data zůstanou beze změny.')}
