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


class AccountSecurityTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.password = 'Account-Safe-Pass-7251!'
        cls.user = User.objects.create_user('user@example.com', cls.password, first_name='Alex')
        cls.other = User.objects.create_user('other@example.com', cls.password)

    def setUp(self):
        from django.core.cache import cache
        cache.clear()

    def login(self, user=None):
        user = user or self.user
        response = self.client.post('/api/v1/auth/login', {'email': user.email, 'password': self.password})
        self.assertEqual(response.status_code, 200, response.data)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + response.data['access'])
        return response.data

    def test_profile_update_cannot_change_identity_or_permissions(self):
        self.login()
        response = self.client.patch('/api/v1/auth/me', {'first_name': 'Dana', 'address': 'Almaty',
            'phone': '+77001234567', 'social_url': 'https://example.com/profile',
            'email': 'other@example.com', 'is_staff': True, 'is_superuser': True}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Dana')
        self.assertEqual(self.user.email, 'user@example.com')
        self.assertFalse(self.user.is_staff)
        self.assertFalse(self.user.is_superuser)
        self.assertNotIn('password', response.data)

    def test_password_change_revokes_old_access_and_refresh(self):
        tokens = self.login()
        new_password = 'New-Neighbor-Password-1842!'
        payload = {'current_password': self.password, 'new_password': new_password,
                   'new_password_repeat': new_password}
        self.assertEqual(self.client.post('/api/v1/auth/password/change', payload).status_code, 200)
        self.assertEqual(self.client.get('/api/v1/auth/me').status_code, 401)
        self.client.credentials()
        self.assertEqual(self.client.post('/api/v1/auth/refresh', {'refresh': tokens['refresh']}).status_code, 401)
        self.assertEqual(self.client.post('/api/v1/auth/login', {'email': self.user.email, 'password': self.password}).status_code, 400)
        self.assertEqual(self.client.post('/api/v1/auth/login', {'email': self.user.email, 'password': new_password}).status_code, 200)

    def test_password_change_requires_current_password_and_valid_confirmation(self):
        self.login()
        for payload in ({'current_password': 'wrong', 'new_password': 'Strong-New-Pass-123!', 'new_password_repeat': 'Strong-New-Pass-123!'},
                        {'current_password': self.password, 'new_password': 'Strong-New-Pass-123!', 'new_password_repeat': 'mismatch'},
                        {'current_password': self.password, 'new_password': '123', 'new_password_repeat': '123'}):
            with self.subTest(payload=payload):
                self.assertEqual(self.client.post('/api/v1/auth/password/change', payload).status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.password))

    def test_logout_rejects_another_users_refresh_token(self):
        other_tokens = self.login(self.other)
        self.login()
        self.assertEqual(self.client.post('/api/v1/auth/logout', {'refresh': other_tokens['refresh']}).status_code, 400)
        self.client.credentials()
        self.assertEqual(self.client.post('/api/v1/auth/refresh', {'refresh': other_tokens['refresh']}).status_code, 200)

    def test_rotated_refresh_cannot_be_reused(self):
        tokens = self.login()
        self.client.credentials()
        response = self.client.post('/api/v1/auth/refresh', {'refresh': tokens['refresh']})
        self.assertEqual(response.status_code, 200)
        self.assertIn('refresh', response.data)
        self.assertEqual(self.client.post('/api/v1/auth/refresh', {'refresh': tokens['refresh']}).status_code, 401)

    def test_account_delete_requires_password_and_invalidates_tokens(self):
        from listings.models import Category, Listing
        tokens = self.login()
        listing = Listing.objects.create(owner=self.user, category=Category.objects.first(), type='offer',
                                         title='Ladder', description='Sturdy ladder', duration='1 day')
        self.assertEqual(self.client.delete('/api/v1/auth/me', {'current_password': 'wrong'}, format='json').status_code, 400)
        self.assertEqual(self.client.delete('/api/v1/auth/me', {'current_password': self.password}, format='json').status_code, 204)
        self.assertFalse(Listing.objects.filter(pk=listing.pk).exists())
        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())
        self.assertEqual(self.client.get('/api/v1/auth/me').status_code, 401)
        self.client.credentials()
        self.assertEqual(self.client.post('/api/v1/auth/refresh', {'refresh': tokens['refresh']}).status_code, 401)

    def test_inactive_account_cannot_login_or_refresh(self):
        tokens = self.login()
        self.user.is_active = False
        self.user.save()
        self.client.credentials()
        self.assertEqual(self.client.post('/api/v1/auth/login', {'email': self.user.email, 'password': self.password}).status_code, 400)
        self.assertEqual(self.client.post('/api/v1/auth/refresh', {'refresh': tokens['refresh']}).status_code, 401)

    def test_malformed_tokens_and_missing_auth_do_not_crash(self):
        self.assertEqual(self.client.get('/api/v1/auth/me').status_code, 401)
        self.assertEqual(self.client.post('/api/v1/auth/refresh', {'refresh': 'not-a-token'}).status_code, 401)
        self.login()
        self.assertEqual(self.client.post('/api/v1/auth/logout', {}, format='json').status_code, 400)
        self.assertEqual(self.client.post('/api/v1/auth/logout', {'refresh': []}, format='json').status_code, 400)

    def test_registration_rejects_weak_password_and_mismatch(self):
        for password, repeat in [('123', '123'), ('Strong-Pass-9241!', 'different')]:
            self.assertEqual(self.client.post('/api/v1/auth/register', {'email': 'new@example.com',
                'password': password, 'password_repeat': repeat}).status_code, 400)

    def test_auth_attempts_are_throttled(self):
        statuses = [self.client.post('/api/v1/auth/login', {'email': 'unknown@example.com', 'password': 'x'}).status_code
                    for _ in range(21)]
        self.assertEqual(statuses[-1], 429)
