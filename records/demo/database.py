"""Verify the second boundary on every new public database connection."""
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db.backends.signals import connection_created
from django.dispatch import receiver

@receiver(connection_created, dispatch_uid='workbase_read_only')
def enforce_read_only(sender, connection, **kwargs):
    if settings.SETUP or settings.TESTING:
        return
    with connection.cursor() as cursor:
        if connection.vendor == 'sqlite':
            cursor.execute('PRAGMA query_only = ON')
            return
        cursor.execute("SELECT rolsuper OR rolcreaterole OR rolcreatedb OR rolbypassrls FROM pg_roles WHERE rolname = current_user")
        if cursor.fetchone()[0]:
            raise ImproperlyConfigured('The public database role must be an unprivileged reader.')
        cursor.execute("""SELECT EXISTS (
          SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
          WHERE n.nspname NOT IN ('pg_catalog', 'information_schema') AND n.nspname NOT LIKE 'pg_toast%'
          AND c.relkind IN ('r','p','v','m','f')
          AND (pg_has_role(current_user, c.relowner, 'MEMBER')
          OR has_table_privilege(c.oid,'INSERT,UPDATE,DELETE,TRUNCATE,TRIGGER,REFERENCES'))
        )""")
        if cursor.fetchone()[0]:
            raise ImproperlyConfigured('The public database role can write to or owns a table. Refusing to serve demo.')
        cursor.execute("""SELECT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname NOT IN ('pg_catalog','information_schema') AND nspname NOT LIKE 'pg_%' AND has_schema_privilege(oid,'CREATE'))""")
        if cursor.fetchone()[0]:
            raise ImproperlyConfigured('Remove CREATE permissions from the public database role.')
        cursor.execute("""SELECT EXISTS (SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE p.prosecdef AND n.nspname NOT IN ('pg_catalog','information_schema') AND has_function_privilege(p.oid,'EXECUTE'))""")
        if cursor.fetchone()[0]:
            raise ImproperlyConfigured('The public role must not execute SECURITY DEFINER functions.')
