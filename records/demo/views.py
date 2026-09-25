from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods, require_POST

@require_http_methods(['GET', 'POST'])
def entry(request):
    if request.method == 'POST':
        request.session['demo_entered'] = True
        return redirect('dashboard')
    return render(request, 'registration/login.html')

@require_POST
def leave(request):
    request.session.flush()
    return redirect('login')

def explanation(request, status=403, title=None):
    return render(request, 'demo_notice.html', {'notice_title': title or _('Tato akce je v ukázce vypnutá.')}, status=status)

def csrf_failure(request, reason=''):
    return explanation(request, 403, _('Stránka vypršela. Obnovte ji a zkuste to znovu.'))
def bad_request(request, exception=None):
    return explanation(request, 400, _('Požadavek se nepodařilo přečíst. Zkuste stránku otevřít znovu.'))
def forbidden(request, exception=None):
    return explanation(request)
def not_found(request, exception=None):
    return explanation(request, 404, _('Tuto stránku jsme nenašli.'))
def server_error(request):
    return explanation(request, 500, _('Ukázka je dočasně nedostupná. Zkuste to za chvíli.'))
