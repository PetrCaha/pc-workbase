from django.http import HttpResponse
from django.urls import include, path
from django.views.i18n import JavaScriptCatalog, set_language
from django.views.decorators.http import require_POST
from rest_framework.routers import DefaultRouter
from records.api import ContactViewSet, CustomerViewSet, JobViewSet
from records.demo import views as demo
router = DefaultRouter()
router.register('customers', CustomerViewSet, basename='api-customer')
router.register('jobs', JobViewSet, basename='api-job')
router.register('contacts', ContactViewSet, basename='api-contact')
urlpatterns = [
    path('health/', lambda request: HttpResponse('ok', content_type='text/plain'), name='health-check'),
    path('login/', demo.entry, name='login'),
    path('logout/', demo.leave, name='logout'),
    path('language/', require_POST(set_language), name='set_language'),
    path('jsi18n/', JavaScriptCatalog.as_view(packages=['records']), name='javascript-catalog'),
    path('api/', include(router.urls)),
    path('', include('records.urls')),
]
handler400 = 'records.demo.views.bad_request'
handler403 = 'records.demo.views.forbidden'
handler404 = 'records.demo.views.not_found'
handler500 = 'records.demo.views.server_error'
