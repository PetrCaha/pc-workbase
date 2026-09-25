"""Owner credentials are entered locally and exist only in child environments."""
import getpass, os, subprocess, sys
from pathlib import Path
from urllib.parse import urlparse
root=Path(__file__).resolve().parent.parent
url=getpass.getpass('Owner URL of the NEW empty WORKBASE database (hidden): ')
parsed=urlparse(url)
if parsed.scheme not in ('postgres','postgresql') or not parsed.hostname:
    raise SystemExit('A PostgreSQL connection string is required.')
print('Target host:',parsed.hostname,'Database:',parsed.path.lstrip('/'))
if input('Type the complete target hostname to confirm it is a NEW demo database: ').strip()!=parsed.hostname:
    raise SystemExit('Cancelled.')
# Inspect before migrations: a wrong/nonempty target must not be modified.
import psycopg
try:
    with psycopg.connect(url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT EXISTS (SELECT 1 FROM pg_tables WHERE schemaname='public')")
            if cur.fetchone()[0]:
                raise SystemExit('Target already contains tables. Nothing was changed. Use a new empty database.')
except psycopg.Error:
    raise SystemExit('Cannot inspect the target database. Check the connection privately; nothing was changed.')
env=dict(os.environ,WORKBASE_SETUP='1',WORKBASE_SETUP_DATABASE_URL=url,DEBUG='false')
env.pop('DATABASE_URL',None)
for command in (['migrate','--noinput'],['seed_demo']):
    subprocess.run([sys.executable,'manage.py',*command],cwd=root,env=env,check=True)
print('Prepared. Remove owner access from the public deployment; configure the reader role next.')
