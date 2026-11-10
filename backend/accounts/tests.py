import secrets
from rest_framework.test import APITestCase
from django.core.cache import cache
from django.utils import timezone
from .models import ResidentialComplex, User

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


class ResidenceVerificationTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.code = secrets.token_urlsafe(16)
        cls.complex = ResidentialComplex(name='Almaly Residence')
        cls.complex.set_code(cls.code)
        cls.complex.save()
        cls.other = ResidentialComplex(name='Central Residence')
        cls.other_code = secrets.token_urlsafe(16)
        cls.other.set_code(cls.other_code)
        cls.other.save()
        cls.user = User.objects.create_user('resident@example.com', 'Resident-Pass-9712!')

    def setUp(self):
        cache.clear()
        self.client.force_authenticate(user=self.user)

    def test_wrong_then_correct_code_updates_profile_without_new_login(self):
        self.assertFalse(self.user.is_resident_verified)
        self.assertEqual(self.client.get('/api/v1/auth/me').status_code, 200)
        complexes = self.client.get('/api/v1/auth/residential-complexes')
        self.assertEqual(complexes.status_code, 200)
        self.assertEqual(len(complexes.data), 2)
        self.assertNotIn('code_hash', complexes.data[0])
        url = '/api/v1/auth/residential-complex/verify'
        payload = {'residential_complex': self.complex.pk, 'code': 'wrong-code'}
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn('code', response.data)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_resident_verified)
        payload['code'] = self.code
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data['is_resident_verified'])
        self.assertEqual(response.data['residential_complex']['id'], self.complex.pk)
        self.assertNotIn('code', response.data)
        self.assertNotIn('code_hash', response.data)
        self.assertEqual(self.client.get('/api/v1/listings').status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_resident_verified)
        self.assertNotEqual(self.complex.code_hash, self.code)

    def test_confirmed_user_can_switch_with_new_code_and_old_listings_are_hidden(self):
        self.client.post('/api/v1/auth/residential-complex/verify',
                         {'residential_complex': self.complex.pk, 'code': self.code})
        from listings.models import Category, Listing
        listing = Listing.objects.create(owner=self.user, category=Category.objects.first(),
            type='offer', title='Old complex listing', description='Old complex', duration='One day')
        self.assertEqual(self.client.post('/api/v1/auth/residential-complex/verify',
                         {'residential_complex': self.other.pk, 'code': 'wrong-code'}).status_code, 400)
        self.assertEqual(self.client.get(f'/api/v1/listings/{listing.pk}').status_code, 200)
        response = self.client.patch('/api/v1/auth/me', {'residential_complex': self.other.pk,
            'is_resident_verified': False, 'residential_verified_at': None}, format='json')
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.residential_complex_id, self.complex.pk)
        self.assertTrue(self.user.is_resident_verified)
        response = self.client.post('/api/v1/auth/residential-complex/verify',
            {'residential_complex': self.other.pk, 'code': self.other_code})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['residential_complex']['id'], self.other.pk)
        self.assertEqual(self.client.get(f'/api/v1/listings/{listing.pk}').status_code, 404)
        self.assertEqual(self.client.get(f'/api/v1/listings/{listing.pk}/contacts').status_code, 404)
        self.assertEqual(self.client.get('/api/v1/listings').data['count'], 0)
        listing.refresh_from_db()
        self.assertIsNotNone(listing.archived_at)
        old_neighbor = User.objects.create_user('old-neighbor@example.com', 'Old-Neigbor-9712!',
            residential_complex=self.complex, residential_verified_at=timezone.now())
        self.client.force_authenticate(user=old_neighbor)
        self.assertEqual(self.client.get(f'/api/v1/listings/{listing.pk}').status_code, 404)
        self.assertEqual(self.client.get('/api/v1/listings').data['count'], 0)
        self.client.force_authenticate(user=self.user)
        new_listing = self.client.post('/api/v1/listings', {'type': 'offer', 'title': 'New complex listing',
            'description': 'New complex', 'category': listing.category_id, 'duration': 'One day'})
        self.assertEqual(new_listing.status_code, 201, new_listing.data)
        self.client.force_authenticate(user=old_neighbor)
        self.assertEqual(self.client.get(f"/api/v1/listings/{new_listing.data['id']}").status_code, 404)
        self.client.force_authenticate(user=self.user)
        self.assertEqual(self.client.post('/api/v1/auth/residential-complex/verify',
            {'residential_complex': self.other.pk, 'code': self.other_code}).status_code, 400)

    def test_verification_attempts_are_throttled(self):
        url = '/api/v1/auth/residential-complex/verify'
        payload = {'residential_complex': self.complex.pk, 'code': 'wrong-code'}
        statuses = [self.client.post(url, payload).status_code for _ in range(6)]
        self.assertEqual(statuses[:5], [400] * 5)
        self.assertEqual(statuses[-1], 429)

    def test_admin_can_create_and_rotate_code_without_exposing_hash(self):
        admin = User.objects.create_superuser('admin@example.com', 'Admin-Pass-7241!')
        first_code, second_code = secrets.token_urlsafe(16), secrets.token_urlsafe(16)
        self.client.force_authenticate(user=None)
        self.client.force_login(admin)
        response = self.client.post('/admin/accounts/residentialcomplex/add/',
            {'name': 'Demo Court', 'is_active': 'on', 'code': first_code, '_save': 'Save'})
        self.assertEqual(response.status_code, 302)
        complex = ResidentialComplex.objects.get(name='Demo Court')
        self.assertTrue(complex.check_code(first_code))
        self.assertNotEqual(complex.code_hash, first_code)
        response = self.client.get(f'/admin/accounts/residentialcomplex/{complex.pk}/change/')
        self.assertNotContains(response, complex.code_hash)
        response = self.client.post(f'/admin/accounts/residentialcomplex/{complex.pk}/change/',
            {'name': 'Demo Court', 'is_active': 'on', 'code': second_code, '_save': 'Save'})
        self.assertEqual(response.status_code, 302)
        complex.refresh_from_db()
        self.assertFalse(complex.check_code(first_code))
        self.assertTrue(complex.check_code(second_code))
