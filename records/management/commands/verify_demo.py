from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from records.demo.integrity import data_digest
class Command(BaseCommand):
    help = 'Read-only verification that all demo data match the reviewed release dataset.'
    def handle(self,*args,**options):
        manifest=settings.BASE_DIR/'demo-manifest.sha256'
        if not manifest.exists() or manifest.read_text().strip()!=data_digest():
            raise CommandError('Demo data do not match the release manifest. Do not publish this database.')
        self.stdout.write(self.style.SUCCESS('All business data, users, role membership and history match the fictional release dataset.'))
