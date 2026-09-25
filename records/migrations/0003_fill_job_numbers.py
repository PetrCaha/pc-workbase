from django.db import migrations


def fill_job_numbers(apps, schema_editor):
    Job = apps.get_model('records', 'Job')
    for job in Job.objects.filter(job_number__isnull=True).order_by('pk'):
        year = job.created_at.year if job.created_at else 2026
        job.job_number = f'Z-{year}-{job.pk:04d}'
        job.save(update_fields=['job_number'])


class Migration(migrations.Migration):
    dependencies = [('records', '0002_customer_status_job_cancellation_reason_and_more')]
    operations = [migrations.RunPython(fill_job_numbers, migrations.RunPython.noop)]
