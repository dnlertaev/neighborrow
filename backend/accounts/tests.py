from unittest.mock import patch
from urllib.parse import parse_qs, urlparse
from django.core import mail
from django.test import override_settings
from rest_framework.test import APITestCase
from .models import User

@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class AuthFlowTests(APITestCase):
    def test_email_required_before_login_and_link_single_use(self):
        password = 'Neighborrow-Safe-Pass-541!'
        payload = {'email': 'NEIGHBOR@example.com', 'password': password,
                   'password_repeat': password, 'first_name': 'Sam'}
        response = self.client.post('/api/v1/auth/register', payload)
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(email='neighbor@example.com')
        self.assertFalse(user.is_active)
        self.assertNotEqual(user.password, password)
        self.assertEqual(self.client.post('/api/v1/auth/login', {'email': user.email,
            'password': password}).status_code, 400)
        self.assertEqual(len(mail.outbox), 1)
        url = mail.outbox[0].body.split()[-1]
        params = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}
        self.assertEqual(self.client.post('/api/v1/auth/verify-email', params).status_code, 200)
        self.assertEqual(self.client.post('/api/v1/auth/verify-email', params).status_code, 400)
        response = self.client.post('/api/v1/auth/login', {'email': user.email, 'password': password})
        self.assertEqual(response.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + response.data['access'])
        self.assertEqual(self.client.get('/api/v1/auth/me').data['email'], user.email)
        self.assertEqual(self.client.post('/api/v1/auth/logout',
            {'refresh': response.data['refresh']}).status_code, 204)

    def test_mail_failure_does_not_leave_unverified_account(self):
        with patch('accounts.views.send_mail', side_effect=RuntimeError('SMTP unavailable')):
            with self.assertRaises(RuntimeError):
                self.client.post('/api/v1/auth/register', {'email': 'sam@example.com',
                    'password': 'Neighborrow-Safe-Pass-541!',
                    'password_repeat': 'Neighborrow-Safe-Pass-541!'})
        self.assertFalse(User.objects.filter(email='sam@example.com').exists())
