#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

# Recolectar archivos estáticos (CSS, JS de admin)
python manage.py collectstatic --no-input

# Ejecutar migraciones en la base de datos por defecto (OLTP)
python manage.py migrate