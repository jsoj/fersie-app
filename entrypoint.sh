#!/bin/sh
set -e

echo "==> Running database migrations..."
python manage.py migrate --noinput

echo "==> Creating default superuser and seeding initial data if needed..."
python manage.py shell << 'EOF'
import os
from django.contrib.auth import get_user_model
from inventory.models import Product

User = get_user_model()
username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'sibele')
email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'contato@fersie.com')
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'Fersie@2026')

if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username=username, email=email, password=password)
    print(f"Superuser '{username}' created successfully!")
else:
    print(f"Superuser '{username}' already exists.")

# Check if inventory is empty
if Product.objects.count() == 0:
    excel_file = "Planilha_Consolidada_Estoque_Fersie.xlsx"
    if os.path.exists(excel_file):
        print(f"Importing initial inventory from {excel_file}...")
        from django.core.management import call_command
        try:
            call_command('import_excel_merchandise', file=excel_file)
            print("Initial inventory imported successfully!")
        except Exception as e:
            print("Import error:", e)
EOF

echo "==> Starting Gunicorn on port 8000..."
exec gunicorn fersie_app.wsgi:application --bind 0.0.0.0:8000 --workers 3
