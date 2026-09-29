from rest_framework.test import APITestCase
from .models import User

class AuthFlowTests(APITestCase):
    def test_register_login_refresh_me_logout(self):
        password = 'Neighborrow-Safe-Pass-541!'
        payload = {'email': 'NEIGHBOR@example.com', 'password': password,
                   'password_repeat': password, 'first_name': 'Sam'}
        response = self.client.post('/api/v1/auth/register', payload)
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(email='neighbor@example.com')
        self.assertTrue(user.is_active)
        self.assertNotEqual(user.password, password)
        self.assertEqual(self.client.post('/api/v1/auth/login', {
            'email': user.email, 'password': 'wrong'}).status_code, 400)
        response = self.client.post('/api/v1/auth/login', {
            'email': 'NEIGHBOR@example.com', 'password': password})
        self.assertEqual(response.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + response.data['access'])
        self.assertEqual(self.client.get('/api/v1/auth/me').data['email'], user.email)
        refreshed = self.client.post('/api/v1/auth/refresh', {
            'refresh': response.data['refresh']})
        self.assertEqual(refreshed.status_code, 200)
        self.assertEqual(self.client.post('/api/v1/auth/logout',
            {'refresh': refreshed.data['refresh']}).status_code, 204)

    def test_duplicate_email_is_rejected(self):
        password = 'Neighborrow-Safe-Pass-541!'
        payload = {'email': 'sam@example.com', 'password': password,
                   'password_repeat': password}
        self.assertEqual(self.client.post('/api/v1/auth/register', payload).status_code, 201)
        payload['email'] = 'SAM@example.com'
        self.assertEqual(self.client.post('/api/v1/auth/register', payload).status_code, 400)
