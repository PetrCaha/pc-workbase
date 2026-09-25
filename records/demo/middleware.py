from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import RequestDataTooBig, TooManyFieldsSent
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils.translation import gettext as _
from .views import explanation

READ_ROUTES = frozenset({'dashboard', 'customer-list', 'customer-detail', 'customer-create', 'customer-update', 'contact-create', 'contact-update', 'job-list', 'job-detail', 'job-create', 'job-update', 'job-transfer', 'jobs-csv', 'job-pdf', 'invoice-detail', 'invoice-create', 'invoice-update', 'invoice-scan', 'user-list', 'api-root', 'api-customer-list', 'api-customer-detail', 'api-job-list', 'api-job-detail', 'api-contact-list', 'api-contact-detail'})
FORM_ROUTES = frozenset({'customer-create', 'customer-update', 'contact-create', 'contact-update', 'job-create', 'job-update', 'job-transfer', 'invoice-create', 'invoice-update', 'invoice-scan'})
PUBLIC_ROUTES = frozenset({'login', 'logout', 'set_language', 'javascript-catalog', 'health-check'})

class DemoBoundaryMiddleware:
    """Reject uploads before CSRF or forms read the request body. Never log it."""
    def __init__(self, get_response):
        self.get_response = get_response
    def __call__(self, request):
        if request.content_type.startswith('multipart/'):
            return explanation(request, 403, _('Nahrávání vlastních souborů je v této ukázce vypnuté.'))
        try:
            size = int(request.META.get('CONTENT_LENGTH') or 0)
        except ValueError:
            return explanation(request, 400)
        if size > settings.DATA_UPLOAD_MAX_MEMORY_SIZE:
            return explanation(request, 413, _('Zadaný obsah je příliš dlouhý.'))
        response = self.get_response(request)
        response['Cache-Control'] = 'private, no-store'
        response['X-Robots-Tag'] = 'noindex, nofollow'
        response['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
        response['Content-Security-Policy'] = "default-src 'self'; img-src 'self' data:; script-src 'self'; style-src 'self'; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; form-action 'self'; base-uri 'self'; object-src 'none'"
        return response

class DemoAccessMiddleware:
    """Explicit read allowlist; POSTs never reach legacy mutation handlers."""
    def __init__(self, get_response):
        self.get_response = get_response
    def __call__(self, request):
        # A session stores only entry state, never an authenticated owner identity.
        if request.session.get('demo_entered'):
            user = get_user_model().objects.filter(username=settings.DEMO_USER, is_active=True, is_staff=False, is_superuser=False).first()
            if user:
                request.user = user
        try:
            return self.get_response(request)
        except (RequestDataTooBig, TooManyFieldsSent):
            return explanation(request, 413, _('Zadaný obsah je příliš dlouhý.'))
    def process_view(self, request, view_func, view_args, view_kwargs):
        name = request.resolver_match.url_name
        if name in PUBLIC_ROUTES:
            return None
        if not request.session.get('demo_entered') or not request.user.is_authenticated:
            return redirect('login')
        if name not in READ_ROUTES:
            return explanation(request)
        if request.method in ('GET', 'HEAD'):
            if name in FORM_ROUTES:
                from .forms import preview_form
                return preview_form(request, name, view_kwargs)
            return None
        if request.method == 'POST' and name in FORM_ROUTES:
            if request.content_type != 'application/x-www-form-urlencoded':
                return explanation(request)
            from .forms import preview_form
            return preview_form(request, name, view_kwargs)
        if request.path.startswith('/api/'):
            return JsonResponse({'detail': _('Změny se v ukázce neukládají.')}, status=405)
        return explanation(request)
