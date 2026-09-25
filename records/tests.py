from io import BytesIO, StringIO
from unittest.mock import patch
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils.translation import override
from pypdf import PdfReader
from .models import Customer, Contact, Job, Invoice, JobChange
from .demo.integrity import data_digest

@override_settings(SECURE_SSL_REDIRECT=False)
class PublicDemoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_demo',stdout=StringIO())
    def setUp(self):
        self.client=Client()
        self.client.post('/login/',{},content_type='application/x-www-form-urlencoded')
        self.before=data_digest()
    def post_form(self,path,data):
        from urllib.parse import urlencode
        return self.client.post(path,urlencode(data),content_type='application/x-www-form-urlencoded')
    def tearDown(self):
        self.assertEqual(self.before,data_digest(),'A public request changed persistent demo data')
    def test_all_read_pages_and_forms(self):
        paths=['/','/zakaznici/','/zakaznici/1/','/zakaznici/novy/','/zakaznici/1/upravit/','/zakaznici/1/kontakty/novy/','/zakaznici/1/kontakty/1/upravit/','/zakazky/','/zakazky/1/','/zakazky/nova/','/zakazky/1/upravit/','/zakazky/1/zmenit-zakaznika/','/zakazky/1/faktury/nova/','/zakazky/1/faktury/nova/ulozit/','/zakazky/1/faktury/1/','/zakazky/1/faktury/1/upravit/','/uzivatele/','/api/','/api/jobs/','/api/contacts/?customer=1','/api/customers/1/']
        for language in ('cs','en'):
            self.client.cookies[settings.LANGUAGE_COOKIE_NAME]=language
            for path in paths:
                with self.subTest(language=language,path=path):
                    response=self.client.get(path)
                    self.assertEqual(response.status_code,200)
    def test_valid_customer_preview_never_calls_save(self):
        with patch('records.forms.CustomerForm.save',side_effect=AssertionError('save called')):
            response=self.post_form('/zakaznici/novy/',{'name':'New example customer','status':'active'})
        self.assertContains(response,'Změny se neuložily.')
        self.assertContains(response,'New example customer')
    def test_edit_customer_stays_unchanged(self):
        self.post_form('/zakaznici/1/upravit/',{'name':'Changed','status':'active'})
    def test_new_contact_and_primary_side_effect_blocked(self):
        self.post_form('/zakaznici/1/kontakty/novy/',{'name':'Another contact','role':'ordering','is_primary':'on'})
    def test_contact_edit_blocked(self):
        self.post_form('/zakaznici/1/kontakty/1/upravit/',{'name':'Changed contact','role':'other'})
    def test_new_job_and_inline_contact_blocked(self):
        response=self.post_form('/zakazky/nova/',{'customer':1,'title':'Example job','status':'new','price':'100','responsible':2,'new_contact_name':'Example person','new_contact_role':'ordering'})
        self.assertEqual(response.status_code,200)
        self.assertNotContains(response,'errorlist')
    def test_job_update_blocked(self):
        self.post_form('/zakazky/1/upravit/',{'customer':1,'title':'Changed job','status':'done','price':'50','responsible':3})
    def test_transfer_blocked(self):
        self.post_form('/zakazky/1/zmenit-zakaznika/',{'customer':2,'contact':2})
    def test_invoice_create_and_update_blocked(self):
        for path in ('/zakazky/1/faktury/nova/ulozit/','/zakazky/1/faktury/1/upravit/'):
            self.post_form(path,{'invoice_number':'CHANGED','currency':'CZK','paid_on':'2026-09-25'})
    def test_all_destructive_routes_and_methods_blocked(self):
        routes=['/zakaznici/1/smazat/','/zakaznici/1/archivovat/','/zakaznici/1/kontakty/1/smazat/','/zakazky/1/smazat/','/zakazky/1/archivovat/','/zakazky/1/faktury/1/smazat/','/uzivatele/novy/','/uzivatele/1/upravit/']
        for path in routes:
            for method in ('get','post','put','patch','delete'):
                with self.subTest(path=path,method=method):
                    self.assertEqual(getattr(self.client,method)(path).status_code,403)
    def test_api_all_writes_blocked(self):
        for resource in ('jobs','customers','contacts'):
            for method in ('post','put','patch','delete'):
                self.assertEqual(getattr(self.client,method)(f'/api/{resource}/1/',data='{}',content_type='application/json').status_code,405)
    def test_uploads_never_reach_parser(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        with patch('records.views.extract_invoice_data',side_effect=AssertionError('Upload parser called')):
            for path in ('/zakazky/1/faktury/nova/','/zakaznici/novy/','/login/'):
                response=self.client.post(path,{'document':SimpleUploadedFile('private.pdf',b'%PDF-secret')})
                self.assertEqual(response.status_code,403)
    def test_large_request_blocked(self):
        response=self.client.post('/zakaznici/novy/','name='+'a'*140000,content_type='application/x-www-form-urlencoded')
        self.assertEqual(response.status_code,413)
    def test_ocr_text_does_not_invoke_parser(self):
        with patch('records.views.parse_invoice_text',side_effect=AssertionError('OCR called')):
            self.post_form('/zakazky/1/faktury/nova/',{'ocr_text':'private content'})
    def test_invalid_form_is_human_and_preserves_input(self):
        response=self.post_form('/zakaznici/novy/',{'name':'Test example','company_id':'x','status':'active'})
        self.assertContains(response,'IČO musí obsahovat přesně 8 číslic.')
        self.assertContains(response,'Test example')
    def test_invalid_customer_id_is_not_server_error(self):
        for path in ('/zakazky/nova/?customer=invalid','/api/contacts/?customer=invalid'):
            self.assertEqual(self.client.get(path).status_code,200)
        self.assertEqual(self.post_form('/zakazky/nova/',{'customer':'invalid','title':'Demo','price':0,'status':'new'}).status_code,200)
    def test_cross_customer_contact_rejected(self):
        response=self.post_form('/zakazky/nova/',{'customer':1,'contact':2,'title':'Demo','price':0,'status':'new'})
        self.assertContains(response,'errorlist')
        self.assertEqual(self.client.get('/zakaznici/1/kontakty/2/upravit/').status_code,404)
        self.assertEqual(self.client.get('/zakazky/2/faktury/1/').status_code,404)
    def test_csrf_enforced(self):
        client=Client(enforce_csrf_checks=True)
        self.assertEqual(client.post('/login/','',content_type='application/x-www-form-urlencoded').status_code,403)
        client.get('/login/')
        token=client.cookies['csrftoken'].value
        self.assertEqual(client.post('/login/',{'csrfmiddlewaretoken':token},content_type='application/x-www-form-urlencoded').status_code,403) # dict is not URL encoded
        from urllib.parse import urlencode
        self.assertEqual(client.post('/login/',urlencode({'csrfmiddlewaretoken':token}),content_type='application/x-www-form-urlencoded').status_code,302)
        self.assertEqual(client.post('/zakazky/nova/','title=hello',content_type='application/x-www-form-urlencoded').status_code,403)
    def test_entry_does_not_update_last_login_or_create_accounts(self):
        self.client.post('/logout/','',content_type='application/x-www-form-urlencoded')
        self.assertEqual(self.client.get('/').status_code,302)
        self.client.post('/login/','',content_type='application/x-www-form-urlencoded')
        self.assertFalse(get_user_model().objects.exclude(last_login=None).exists())
    def test_forged_session_does_not_enter(self):
        client=Client();client.cookies[settings.SESSION_COOKIE_NAME]='demo_entered=true'
        self.assertEqual(client.get('/').status_code,302)
    def test_admin_and_ares_unavailable(self):
        self.assertEqual(self.client.get('/admin/').status_code,404)
        with patch('records.views.urlopen',side_effect=AssertionError('External request')):
            self.assertEqual(self.client.get('/ares/hledat/?q=test').status_code,403)
    def test_language_switch_preserves_page_and_filters(self):
        response=self.post_form('/language/',{'language':'en','next':'/zakazky/?view=all&sort=price'})
        self.assertEqual(response.url,'/zakazky/?view=all&sort=price')
        self.assertContains(self.client.get(response.url),'Jobs')
        response=self.post_form('/language/',{'language':'cs','next':'https://evil.example/'})
        self.assertFalse(response.url.startswith('https://evil.example'))
    def test_english_content_and_validation(self):
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME]='en'
        self.assertContains(self.client.get('/zakazky/1/'),'Cafe back-room fit-out')
        self.assertContains(self.client.get('/zakazky/1/faktury/1/'),'Awaiting payment')
        response=self.post_form('/zakaznici/novy/',{'company_id':'invalid','status':'active'})
        self.assertContains(response,'This field is required.')
        self.assertContains(response,'The company ID must contain exactly 8 digits.')
        self.assertContains(self.client.get('/api/jobs/1/'),'Cafe back-room fit-out')
        self.assertContains(self.client.get('/jsi18n/'),'Loading')
    def test_english_search(self):
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME]='en'
        self.assertContains(self.client.get('/zakazky/?q=fit-out'),'Cafe back-room fit-out')
    def test_export_content_in_both_languages(self):
        for language,label in (('cs','Odpovědná osoba'),('en','Responsible person')):
            self.client.cookies[settings.LANGUAGE_COOKIE_NAME]=language
            response=self.client.get('/zakazky/1/pdf/')
            text=''.join(page.extract_text() for page in PdfReader(BytesIO(b''.join(response.streaming_content))).pages)
            self.assertIn(label," ".join(text.split()));self.assertIn('Marek',text)
            csv=self.client.get('/zakazky/export.csv').content.decode()
            self.assertIn('WB-2026-001',csv)
    def test_payment_states_and_dataset_integrity(self):
        self.assertEqual([x.payment_status for x in Invoice.objects.order_by('pk')],['pending','paid','overdue'])
        self.assertEqual((Customer.objects.count(),Job.objects.count(),Invoice.objects.count()),(8,12,3))
        call_command('verify_demo',stdout=StringIO())
    def test_seed_refuses_existing_database(self):
        with self.assertRaises(CommandError):call_command('seed_demo',stdout=StringIO())
    def test_no_external_scripts_or_analytics(self):
        response=self.client.get('/')
        for forbidden in ('google-analytics','tesseract','cdn.jsdelivr','<script src="http'):
            self.assertNotContains(response,forbidden)
        self.assertIn("form-action 'self'",response['Content-Security-Policy'])
    def test_portfolio_cta(self):
        self.assertContains(self.client.get('/'),'https://petrcaha.cz/#contact')
    def test_csrf_errors_do_not_leak_technical_details(self):
        with override_settings(DEBUG=False):
            response=Client(enforce_csrf_checks=True).post('/login/','',content_type='application/x-www-form-urlencoded')
            self.assertContains(response,'Stránka vypršela',status_code=403)

class PreservedBehaviourTests(TestCase):
    """Checks for inherited business rules, independent of the public HTTP layer."""
    def test_customer_contact_must_match_job(self):
        from .forms import JobForm
        a=Customer.objects.create(name='Example A');b=Customer.objects.create(name='Example B')
        contact=Contact.objects.create(customer=b,name='Example contact')
        form=JobForm({'customer':a.pk,'contact':contact.pk,'title':'Example','status':'new','price':'1'})
        self.assertFalse(form.is_valid())
    def test_completed_job_has_date_and_customer_is_protected(self):
        from django.db.models.deletion import ProtectedError
        customer=Customer.objects.create(name='Fictional test')
        job=Job.objects.create(customer=customer,title='Fictional job',status='done')
        self.assertIsNotNone(job.completed_at)
        with self.assertRaises(ProtectedError):customer.delete()
    def test_invoice_relationship_allows_multiple(self):
        customer=Customer.objects.create(name='Fictional test')
        job=Job.objects.create(customer=customer,title='Fictional job')
        Invoice.objects.create(job=job,invoice_number='TEST-1')
        Invoice.objects.create(job=job,invoice_number='TEST-2')
        self.assertEqual(job.invoices.count(),2)
    def test_csv_formula_is_escaped(self):
        from .permissions import set_user_role,ROLE_ADMIN
        user=get_user_model().objects.create(username='anna.demo',password='!disabled')
        set_user_role(user,ROLE_ADMIN)
        customer=Customer.objects.create(name='=FORMULA()')
        Job.objects.create(customer=customer,title='@FORMULA()')
        client=Client();client.post('/login/','',content_type='application/x-www-form-urlencoded')
        csv=client.get('/zakazky/export.csv').content.decode()
        self.assertIn("'=FORMULA()",csv);self.assertIn("'@FORMULA()",csv)
    def test_pdf_escapes_markup(self):
        from .permissions import set_user_role,ROLE_ADMIN
        user=get_user_model().objects.create(username='anna.demo',password='!disabled')
        set_user_role(user,ROLE_ADMIN)
        customer=Customer.objects.create(name='<example>')
        job=Job.objects.create(customer=customer,title='A & B <test>',description='<not markup>')
        client=Client();client.post('/login/','',content_type='application/x-www-form-urlencoded')
        response=client.get(f'/zakazky/{job.pk}/pdf/')
        self.assertEqual(response.status_code,200)
        self.assertIn('<not markup>',PdfReader(BytesIO(b''.join(response.streaming_content))).pages[0].extract_text())

@override_settings(SECURE_SSL_REDIRECT=False)
class AdditionalBoundaryTests(TestCase):
    @classmethod
    def setUpTestData(cls):call_command('seed_demo',stdout=StringIO())
    def test_html_input_is_escaped_without_persistence(self):
        from urllib.parse import urlencode
        client=Client();client.post('/login/','',content_type='application/x-www-form-urlencoded')
        before=data_digest()
        response=client.post('/zakaznici/novy/',urlencode({'name':'<script>alert(1)</script>','status':'active'}),content_type='application/x-www-form-urlencoded')
        self.assertNotContains(response,'<script>alert(1)</script>')
        self.assertContains(response,'&lt;script&gt;')
        self.assertEqual(before,data_digest())
    @override_settings(DEBUG=False)
    def test_missing_page_is_a_human_response(self):
        response=Client().get('/does-not-exist/')
        self.assertContains(response,'Tuto stránku jsme nenašli.',status_code=404)
        self.assertNotContains(response,'urlpatterns',status_code=404)
    def test_method_override_cannot_bypass_policy(self):
        from urllib.parse import urlencode
        client=Client();client.post('/login/','',content_type='application/x-www-form-urlencoded')
        before=data_digest()
        response=client.post('/zakazky/1/smazat/',urlencode({'_method':'GET'}),content_type='application/x-www-form-urlencoded',HTTP_X_HTTP_METHOD_OVERRIDE='GET')
        self.assertEqual(response.status_code,403)
        self.assertEqual(before,data_digest())
    def test_pdf_and_csv_are_safe_head_requests(self):
        client=Client();client.post('/login/','',content_type='application/x-www-form-urlencoded')
        before=data_digest()
        for path in ('/zakazky/1/pdf/','/zakazky/export.csv'):
            self.assertEqual(client.head(path).status_code,200)
        self.assertEqual(before,data_digest())
