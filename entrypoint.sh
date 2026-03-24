#!/bin/sh
set -e

until python manage.py migrate --noinput
do
  sleep 1
done

exec "$@"
