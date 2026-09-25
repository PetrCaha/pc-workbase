#!/usr/bin/env bash
set -euo pipefail
python -m pip install -r requirements.txt
python scripts/compile_translations.py
# This build never migrates or seeds a database and never needs owner credentials.
WORKBASE_SETUP=1 python manage.py collectstatic --no-input
