from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction, DatabaseError
from django.conf import settings
from records.demo.integrity import data_digest

class Command(BaseCommand):
    help = 'Verify that the public database connection refuses UPDATE, even with zero matching rows.'
    def handle(self,*args,**options):
        if settings.SETUP or settings.TESTING:
            raise CommandError('Run with public runtime settings, not setup or test settings.')
        before=data_digest()
        tables=['records_customer','records_contact','records_job','records_invoice','records_jobchange','records_customerchange','auth_user','auth_group','auth_user_groups','auth_permission','auth_group_permissions','auth_user_user_permissions']
        for table in tables:
            try:
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute(f'UPDATE {connection.ops.quote_name(table)} SET id=id WHERE 1=0')
            except DatabaseError as exc:
                code=getattr(exc.__cause__,'sqlstate',None)
                if connection.vendor=='postgresql' and code not in ('42501','25006'):
                    raise CommandError('Unexpected database error while checking permissions.') from exc
                if connection.vendor=='sqlite' and 'readonly' not in str(exc).lower() and 'read-only' not in str(exc).lower():
                    raise
            else:
                raise CommandError(f'Write accepted for {table}. Do not publish this configuration.')
        if before!=data_digest():
            raise CommandError('Data fingerprint changed during verification.')
        self.stdout.write(self.style.SUCCESS(f'Writes refused on {len(tables)} business/authentication tables. Data unchanged.'))
