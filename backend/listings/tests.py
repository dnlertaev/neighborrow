from datetime import timedelta
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APITestCase
from accounts.models import User
from .models import Activity, Category, Interest, Listing


class ListingAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user('owner@example.com', 'Owner-pass-7241!', first_name='Sam',
                                            last_name='Brown', phone='+77000000000', address='Private street')
        cls.neighbor = User.objects.create_user('neighbor@example.com', 'Neighbor-pass-7341!')
        cls.third = User.objects.create_user('third@example.com', 'Third-pass-8931!')
        cls.tools = Category.objects.get(slug='tools')
        cls.garden = Category.objects.get(slug='garden')
        cls.offer = Listing.objects.create(owner=cls.owner, type='offer', title='Small hammer',
            description='Useful for hanging shelves', category=cls.tools, duration='2 hours',
            contact_phone='+77001234567', latitude=43.25, longitude=76.95)

    def setUp(self):
        cache.clear()

    def payload(self, **extra):
        return {'title': 'Garden hose', 'description': 'For watering the plants', 'type': 'request',
                'category': self.garden.pk, 'duration': 'Today, 2 hours', **extra}

    def authenticate(self, user=None):
        self.client.force_authenticate(user=user or self.owner)

    def test_public_feed_hides_profile_and_contacts(self):
        response = self.client.get('/api/v1/listings')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        item = response.data['results'][0]
        self.assertEqual(item['owner'], {'id': self.owner.pk, 'display_name': 'Sam B.'})
        self.assertNotIn('contact_phone', item)
        self.assertNotIn('latitude', item)
        self.assertNotIn('email', item['owner'])
        self.assertNotIn('address', item['owner'])
        self.assertIsNone(item['distance_km'])

    def test_create_requires_authentication(self):
        self.assertEqual(self.client.post('/api/v1/listings', self.payload()).status_code, 401)
        self.assertEqual(Listing.objects.count(), 1)

    def test_create_sets_owner_and_records_activity(self):
        self.authenticate(self.neighbor)
        response = self.client.post('/api/v1/listings', self.payload(owner=self.owner.pk))
        self.assertEqual(response.status_code, 201, response.data)
        listing = Listing.objects.get(pk=response.data['id'])
        self.assertEqual(listing.owner, self.neighbor)
        self.assertTrue(response.data['mine'])
        self.assertTrue(Activity.objects.filter(recipient=self.neighbor, listing=listing, type='request_created').exists())

    def test_other_user_cannot_edit_or_delete(self):
        self.authenticate(self.neighbor)
        url = f'/api/v1/listings/{self.offer.pk}'
        self.assertEqual(self.client.patch(url, {'title': 'Hacked'}).status_code, 403)
        self.assertEqual(self.client.delete(url).status_code, 403)
        self.offer.refresh_from_db()
        self.assertEqual(self.offer.title, 'Small hammer')

    def test_owner_can_update_and_delete(self):
        self.authenticate()
        url = f'/api/v1/listings/{self.offer.pk}'
        self.assertEqual(self.client.patch(url, {'available': False}, format='json').status_code, 200)
        self.assertEqual(self.client.delete(url).status_code, 204)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(Activity.objects.filter(type='listing_deleted', listing=None).count(), 1)

    def test_filters_search_and_mine(self):
        self.authenticate(self.neighbor)
        self.client.post('/api/v1/listings', self.payload())
        response = self.client.get('/api/v1/listings', {'type': 'request', 'category': self.garden.pk, 'search': 'HOSE', 'mine': 'true'})
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['title'], 'Garden hose')
        self.assertEqual(self.client.get('/api/v1/listings', {'type': 'offer', 'mine': 'true'}).data['count'], 0)
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get('/api/v1/listings', {'mine': 'true'}).status_code, 401)

    def test_distance_filter_and_missing_location(self):
        Listing.objects.create(owner=self.neighbor, type='offer', title='Far hammer', description='Far away',
                               category=self.tools, duration='1 day', latitude=44.25, longitude=76.95)
        Listing.objects.create(owner=self.neighbor, type='offer', title='Unknown location', description='No coordinates',
                               category=self.tools, duration='1 day')
        response = self.client.get('/api/v1/listings', {'latitude': 43.25, 'longitude': 76.95,
                                                      'radius_km': 2, 'ordering': 'nearest'})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['count'], 1)
        self.assertLess(response.data['results'][0]['distance_km'], 0.01)
        response = self.client.get('/api/v1/listings', {'latitude': 43.25, 'longitude': 76.95, 'ordering': 'nearest'})
        self.assertEqual(response.data['results'][-1]['title'], 'Unknown location')
        self.assertIsNone(response.data['results'][-1]['distance_km'])

    def test_invalid_query_parameters_return_400(self):
        for query in ({'type': 'other'}, {'category': 'x'}, {'latitude': 95, 'longitude': 0},
                      {'radius_km': 1}, {'ordering': 'nearest'}, {'latitude': 'nan', 'longitude': 0},
                      {'latitude': 0, 'longitude': 0, 'radius_km': 'inf'}):
            with self.subTest(query=query):
                self.assertEqual(self.client.get('/api/v1/listings', query).status_code, 400)

    def test_invalid_listing_data(self):
        self.authenticate()
        for fields in ({'title': '  '}, {'category': 99999}, {'type': 'other'},
                       {'latitude': 43}, {'latitude': 91, 'longitude': 70},
                       {'needed_until': str(timezone.localdate() - timedelta(days=1))},
                       {'image_url': 'ftp://example.com/photo.png'}, {'contact_social': 'javascript:alert(1)'}):
            with self.subTest(fields=fields):
                self.assertEqual(self.client.post('/api/v1/listings', self.payload(**fields), format='json').status_code, 400)
        self.assertEqual(self.client.patch(f'/api/v1/listings/{self.offer.pk}', {'type': 'request'}).status_code, 400)

    def test_contacts_require_login_and_no_private_profile_fallback(self):
        url = f'/api/v1/listings/{self.offer.pk}/contacts'
        self.assertEqual(self.client.get(url).status_code, 401)
        self.authenticate(self.neighbor)
        self.assertEqual(self.client.get(url).data['phone'], '+77001234567')
        self.offer.contact_phone = ''
        self.offer.save()
        self.assertEqual(self.client.get(url).data['phone'], '')

    def test_matches_exclude_wrong_type_category_owner_unavailable_and_expired(self):
        request = Listing.objects.create(owner=self.neighbor, type='request', title='Need hammer',
            description='For shelves', category=self.tools, duration='2 hours')
        common = {'title': 'Hammer', 'description': 'Matching', 'category': self.tools, 'duration': 'Today',
                  'owner': self.third, 'type': 'offer'}
        for fields in ({'type': 'request'}, {'category': self.garden}, {'owner': self.neighbor},
                       {'available': False}, {'needed_until': timezone.localdate() - timedelta(days=1)}):
            Listing.objects.create(**(common | fields))
        less_relevant = Listing.objects.create(**(common | {'title': 'Screwdriver'}))
        response = self.client.get(f'/api/v1/listings/{request.pk}/matches')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([x['id'] for x in response.data['results']], [self.offer.pk, less_relevant.pk])
        request.available = False
        request.save()
        self.assertEqual(self.client.get(f'/api/v1/listings/{request.pk}/matches').data['count'], 0)

    def test_interest_is_idempotent_and_activity_is_private(self):
        url = f'/api/v1/listings/{self.offer.pk}/interest'
        self.assertEqual(self.client.post(url).status_code, 401)
        self.authenticate(self.neighbor)
        self.assertEqual(self.client.post(url).status_code, 201)
        self.assertEqual(self.client.post(url).status_code, 200)
        self.assertEqual(Interest.objects.count(), 1)
        self.assertEqual(Activity.objects.count(), 2)
        self.assertEqual(self.client.get('/api/v1/activity').data['count'], 1)
        self.authenticate(self.third)
        self.assertEqual(self.client.get('/api/v1/activity').data['count'], 0)
        self.authenticate()
        response = self.client.get('/api/v1/activity')
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['actor']['id'], self.neighbor.pk)

    def test_cannot_respond_to_own_or_unavailable_listing(self):
        url = f'/api/v1/listings/{self.offer.pk}/interest'
        self.authenticate()
        self.assertEqual(self.client.post(url).status_code, 400)
        self.authenticate(self.neighbor)
        self.offer.available = False
        self.offer.save()
        self.assertEqual(self.client.post(url).status_code, 400)
        self.offer.available = True
        self.offer.needed_until = timezone.localdate() - timedelta(days=1)
        self.offer.save()
        self.assertEqual(self.client.post(url).status_code, 400)

    def test_seeded_categories_are_public_but_read_only(self):
        response = self.client.get('/api/v1/categories')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 6)
        self.assertEqual(self.client.post('/api/v1/categories', {'name': 'Unapproved'}).status_code, 405)

    def test_pagination_and_inactive_owner(self):
        response = self.client.get('/api/v1/listings', {'page_size': 1})
        self.assertEqual(len(response.data['results']), 1)
        self.owner.is_active = False
        self.owner.save()
        self.assertEqual(self.client.get('/api/v1/listings').data['count'], 0)
        self.assertEqual(self.client.get(f'/api/v1/listings/{self.offer.pk}').status_code, 404)

    def test_cors_allows_only_configured_origin(self):
        response = self.client.options('/api/v1/listings', HTTP_ORIGIN='http://localhost:3000',
                                      HTTP_ACCESS_CONTROL_REQUEST_METHOD='POST',
                                      HTTP_ACCESS_CONTROL_REQUEST_HEADERS='authorization,content-type')
        self.assertEqual(response.headers['Access-Control-Allow-Origin'], 'http://localhost:3000')
        blocked = self.client.options('/api/v1/listings', HTTP_ORIGIN='https://unapproved.example',
                                     HTTP_ACCESS_CONTROL_REQUEST_METHOD='POST')
        self.assertNotIn('Access-Control-Allow-Origin', blocked.headers)

    def test_response_status_survives_new_requests_and_is_user_specific(self):
        self.authenticate(self.neighbor)
        self.client.post(f'/api/v1/listings/{self.offer.pk}/interest')
        self.assertTrue(self.client.get(f'/api/v1/listings/{self.offer.pk}').data['has_responded'])
        self.assertTrue(self.client.get('/api/v1/listings').data['results'][0]['has_responded'])
        self.authenticate(self.third)
        self.assertFalse(self.client.get(f'/api/v1/listings/{self.offer.pk}').data['has_responded'])
        self.client.force_authenticate(user=None)
        self.assertFalse(self.client.get(f'/api/v1/listings/{self.offer.pk}').data['has_responded'])

    def test_available_filter_excludes_expired_listings(self):
        self.offer.needed_until = timezone.localdate() - timedelta(days=1)
        self.offer.save()
        self.assertEqual(self.client.get('/api/v1/listings', {'available': 'true'}).data['count'], 0)
        self.assertEqual(self.client.get('/api/v1/listings', {'available': 'false'}).data['count'], 1)
