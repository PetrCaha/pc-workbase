"""Populate an EMPTY, dedicated WORKBASE database. Never import customer data."""
from datetime import date, datetime, timedelta
from decimal import Decimal
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from records.models import Customer, Contact, Job, Invoice, JobChange, CustomerChange
from records.permissions import ROLE_ADMIN, ROLE_MANAGER, ROLE_MEMBER, set_user_role

class Command(BaseCommand):
    help = 'Prepare fictional WORKBASE data in an empty dedicated database (offline only).'
    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.SETUP and not settings.TESTING:
            raise CommandError('Run offline with WORKBASE_SETUP=1. Public runtime is read-only.')
        if any(model.objects.exists() for model in (get_user_model(), Customer, Contact, Job, Invoice, JobChange, CustomerChange)):
            raise CommandError('Database is not empty. Refusing to merge or replace existing records.')
        reference = date.fromisoformat(settings.DEMO_REFERENCE_DATE)
        users=[]
        for username,first,last,role in [('anna.demo','Anna','Vzorová',ROLE_ADMIN),('marek.demo','Marek','Ukázkový',ROLE_MANAGER),('eva.demo','Eva','Modelová',ROLE_MEMBER)]:
            user=get_user_model().objects.create(username=username,first_name=first,last_name=last,email=username+'@example.com',password='!workbase-demo-no-password-login',is_staff=False,is_superuser=False)
            set_user_role(user,role); users.append(user)
        names=['Kavárna U Papírového měsíce','Ateliér Modrý provázek','Penzion Tichý kompas','Dílna Sedm koleček','Studio Malý obzor','Květinářství Zelená tečka','Prodejna Dřevěná vlaštovka','Kancelář Jasný list']
        contacts=['Klára Ukázková','David Modelový','Lenka Vzorová','Adam Ukázkový','Nina Modelová','Tomáš Vzorový','Iva Ukázková','Robin Modelový']
        customers=[]; persons=[]
        for i,(name,person) in enumerate(zip(names,contacts),1):
            customer=Customer.objects.create(name=name,email=f'customer{i}@example.com',street=f'Ukázková {i}',city='Modelov (smyšlené město)',postal_code='',note='Smyšlený zákazník pro ukázku pracovního prostoru.',status=Customer.Status.INACTIVE if i==7 else Customer.Status.ACTIVE)
            contact=Contact.objects.create(customer=customer,name=person,email=f'contact{i}@example.com',role=Contact.Role.ORDERING,is_primary=True,note='Ukázková kontaktní osoba, nejde o skutečný kontakt.')
            customers.append(customer);persons.append(contact)
            CustomerChange.objects.create(customer=customer,user=users[0],action=CustomerChange.Action.CREATED)
        jobs=[
            (0,'Úprava zázemí kavárny','in_progress',38500,7,1,'Montáž pracovního pultu a polic v zázemí kavárny. Rozměry jsou potvrzené, materiál připravený. Vstup domluven před otevřením v 7:00.'),
            (0,'Servis dveří','done',2400,-20,2,'Seřízení závěsů a výměna těsnění. Předáno kontaktní osobě bez připomínek.'),
            (1,'Montáž osvětlení','new',12600,12,1,'Instalace pracovního osvětlení nad montážním stolem. Před zahájením potvrdit rozmístění.'),
            (1,'Úprava pracovních stolů','done',8900,-8,2,'Doplnění ochranných hran a úprava výšky dvou pracovních stolů.'),
            (2,'Výměna svítidel','waiting',16400,18,1,'Čekáme na potvrzení termínu dodání vybraných svítidel.'),
            (3,'Montáž regálů','in_progress',21800,4,2,'Sestavení a kotvení regálů pro lehký materiál. Zbývá dokončit poslední sekci.'),
            (3,'Oprava pracovního pultu','done',5600,-12,1,'Výměna poškozené pracovní desky a kontrola uchycení.'),
            (4,'Úprava recepce','new',18500,21,1,'Příprava rozměrů a návrhu úložných polic pro recepci.'),
            (5,'Montáž polic','done',6200,-5,2,'Instalace tří polic pro vystavení lehkého zboží. Provozovna převzata uklizená.'),
            (6,'Úprava zázemí prodejny','cancelled',9900,0,1,'Zákazník odložil úpravy provozovny. Práce nebyly zahájeny.'),
            (6,'Starší montáž stojanu','done',4100,-60,2,'Dokončená starší zakázka uložená v archivu.'),
            (7,'Kabelové vedení','waiting',7400,14,2,'Čekáme na finální rozmístění pracovních míst před montáží lišt.'),
        ]
        created=[]
        for i,(c,title,status,price,days,owner,description) in enumerate(jobs,1):
            job=Job.objects.create(customer=customers[c],contact=persons[c],responsible=users[owner],job_number=f'WB-2026-{i:03d}',title=title,status=status,price=price,due_date=reference+timedelta(days=days),completed_at=reference+timedelta(days=days) if status=='done' else None,description=description,is_archived=i==11)
            created.append(job)
            JobChange.objects.create(job=job,user=users[0],action=JobChange.Action.CREATED)
        JobChange.objects.create(job=created[0],user=users[1],action=JobChange.Action.UPDATED,changes={'status':{'from':'Nová','to':'Probíhá'},'responsible':{'from':'—','to':users[1].get_full_name()}},reason='Rozměry potvrzeny, tým může zahájit montáž.')
        for i,(job,amount,due,paid,items) in enumerate([(created[0],38500,14,None,'Pracovní pult a police, materiál a montáž.'),(created[1],2400,-10,-12,'Seřízení dveří a výměna těsnění.'),(created[3],8900,-3,None,'Úprava dvou pracovních stolů a ochranné hrany.')],1):
            invoice=Invoice.objects.create(job=job,supplier_name='Montáže Modelov — ukázkový tým',supplier_address='Dílenská 1, Modelov (smyšlená adresa)',customer_header=job.customer.name,invoice_number=f'DEMO-2026-{i:03d}',variable_symbol='',issue_date=reference-timedelta(days={1:5,2:19,3:7}[i]),taxable_date=reference-timedelta(days={1:5,2:19,3:7}[i]),due_date=reference+timedelta(days=due),paid_on=reference+timedelta(days=paid) if paid else None,payment_method='Ukázkový bankovní převod — neplaťte',items_text=items,total_amount=Decimal(amount),currency='CZK',note='Smyšlený doklad pro portfolio. Nejde o výzvu k platbě.',raw_text='UKÁZKOVÝ DOKLAD — BEZ PLATEBNÍCH ÚDAJŮ',created_by=users[0],updated_by=users[1])
            JobChange.objects.create(job=job,user=users[0],action=JobChange.Action.INVOICE_CREATED,changes={'invoice_number':{'from':'—','to':invoice.invoice_number}})
        # Fixed reference dates keep both language variants and exports coherent.
        moment=timezone.make_aware(datetime(2026,9,1,9,0))
        for i,job in enumerate(created):
            Job.objects.filter(pk=job.pk).update(created_at=moment+timedelta(days=10 if i==0 else i//2),updated_at=moment+timedelta(days=23))
        for model in (Customer,Invoice):
            model.objects.update(created_at=moment,updated_at=moment+timedelta(days=23))
        for item in JobChange.objects.select_related('job'):
            stamp = item.job.created_at + timedelta(hours=1) if item.action == 'created' else moment + timedelta(days=23, hours=item.pk)
            JobChange.objects.filter(pk=item.pk).update(created_at=stamp)
        CustomerChange.objects.update(created_at=moment)
        get_user_model().objects.update(date_joined=moment)
        from records.demo.integrity import data_digest
        path=settings.BASE_DIR/'demo-manifest.sha256'
        expected=data_digest()
        if path.exists() and path.read_text().strip()!=expected:
            raise CommandError('Dataset differs from release manifest. Review the dataset before release.')
        if not path.exists():
            path.write_text(expected+'\n')
        self.stdout.write(self.style.SUCCESS('Prepared 8 fictional customers, 12 jobs, 3 workers and 3 invoices. No password login.'))
