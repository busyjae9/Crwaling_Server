.venv/Scripts/Activate.ps1

# gunicorn --bind 0.0.0.0:6584 manage
waitress-serve --listen=*:6584 manage:app
# hupper -m waitress --listen=*:6584 manage:app
# flask run -h "0.0.0.0" -p 6584 --reload --debugger

# python manage.py