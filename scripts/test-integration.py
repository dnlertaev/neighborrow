"""Run the actual frontend API client against Django with an isolated temporary DB.
Usage: python scripts/test-integration.py FRONTEND_PATH COMPILED_API_CLIENT_PATH
"""
import os
import secrets
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from wsgiref.simple_server import WSGIRequestHandler, make_server

ROOT = Path(__file__).resolve().parent.parent
frontend = Path(sys.argv[1]).resolve()
client_module = Path(sys.argv[2]).resolve()
sys.path.insert(0, str(ROOT / 'backend'))
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
os.environ['DJANGO_DEBUG'] = '1'
from django.conf import settings

with tempfile.TemporaryDirectory(prefix='neighborrow-integration-') as temporary:
    settings.DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': str(Path(temporary) / 'test.sqlite3')}}
    settings.ALLOWED_HOSTS = ['127.0.0.1', 'localhost']
    settings.SECURE_SSL_REDIRECT = False
    import django
    django.setup()
    from django.core.management import call_command
    from django.core.wsgi import get_wsgi_application
    from django.db import connections
    call_command('migrate', verbosity=0, interactive=False)
    from accounts.models import ResidentialComplex

    complex_a_code = secrets.token_urlsafe(16)
    complex_b_code = secrets.token_urlsafe(16)
    for name, code in (('Integration Complex A', complex_a_code),
                       ('Integration Complex B', complex_b_code)):
        complex = ResidentialComplex(name=name)
        complex.set_code(code)
        complex.save()

    class QuietHandler(WSGIRequestHandler):
        def log_message(self, *args):
            pass

    with make_server('127.0.0.1', 0, get_wsgi_application(), handler_class=QuietHandler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            env = {**os.environ, 'API_CLIENT_MODULE': str(client_module),
                   'TEST_API_URL': f'http://127.0.0.1:{server.server_port}/api/v1',
                   'TEST_COMPLEX_A_CODE': complex_a_code,
                   'TEST_COMPLEX_B_CODE': complex_b_code}
            result = subprocess.run(['node', str(frontend / 'tests/api-integration.mjs')], env=env, check=False)
        finally:
            server.shutdown()
            thread.join(timeout=5)
            connections.close_all()
    raise SystemExit(result.returncode)
