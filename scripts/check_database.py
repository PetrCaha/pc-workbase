import getpass, os, secrets, subprocess, sys
from pathlib import Path
root=Path(__file__).resolve().parent.parent
url=getpass.getpass('WORKBASE reader database URL (hidden): ')
env=dict(os.environ,DATABASE_URL=url,DEBUG='false',SECRET_KEY=secrets.token_urlsafe(64))
for key in ('WORKBASE_SETUP','WORKBASE_SETUP_DATABASE_URL','WORKBASE_TESTING'):env.pop(key,None)
for command in ('verify_demo','verify_read_only'):
    subprocess.run([sys.executable,'manage.py',command],cwd=root,env=env,check=True)
