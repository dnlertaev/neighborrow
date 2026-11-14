import math
from django.utils import timezone
from rest_framework import serializers
from accounts.models import User
from .models import Activity, Category, Listing


class PublicUserSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'display_name')

    def get_display_name(self, obj):
        return f'{obj.first_name} {obj.last_name[:1] + "." if obj.last_name else ""}'.strip() or 'Neighbor'


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ('id', 'name', 'slug')


class ListingSerializer(serializers.ModelSerializer):
    owner = PublicUserSerializer(read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    distance_km = serializers.SerializerMethodField()
    mine = serializers.SerializerMethodField()
    has_responded = serializers.SerializerMethodField()
    contact_phone = serializers.CharField(max_length=32, allow_blank=True, required=False, write_only=True)
    contact_social = serializers.URLField(max_length=500, allow_blank=True, required=False, write_only=True)

    class Meta:
        model = Listing
        fields = ('id', 'type', 'title', 'description', 'category', 'category_name', 'owner',
                  'condition', 'duration', 'needed_until', 'available', 'neighborhood',
                  'latitude', 'longitude', 'distance_km', 'image_url', 'contact_phone',
                  'contact_social', 'created_at', 'updated_at', 'mine', 'has_responded')
        read_only_fields = ('id', 'created_at', 'updated_at')
        extra_kwargs = {'latitude': {'write_only': True}, 'longitude': {'write_only': True}}

    def get_has_responded(self, obj):
        return bool(getattr(obj, 'has_responded', False))

    def get_mine(self, obj):
        request = self.context.get('request')
        return bool(request and request.user.is_authenticated and obj.owner_id == request.user.pk)

    def get_distance_km(self, obj):
        distance = getattr(obj, 'distance_km', None)
        return round(distance, 2) if distance is not None else None

    def validate(self, attrs):
        lat = attrs.get('latitude', getattr(self.instance, 'latitude', None))
        lon = attrs.get('longitude', getattr(self.instance, 'longitude', None))
        if (lat is None) != (lon is None):
            raise serializers.ValidationError({'latitude': 'Provide both coordinates or set both to null.'})
        if lat is not None and (not math.isfinite(lat) or not math.isfinite(lon)):
            raise serializers.ValidationError({'latitude': 'Coordinates must be finite numbers.'})
        for key in ('contact_social', 'image_url'):
            if attrs.get(key) and not attrs[key].startswith(('https://', 'http://')):
                raise serializers.ValidationError({key: 'Use an HTTP or HTTPS link.'})
        if attrs.get('needed_until') and attrs['needed_until'] < timezone.localdate():
            raise serializers.ValidationError({'needed_until': 'Choose today or a later date.'})
        if self.instance and 'type' in attrs and attrs['type'] != self.instance.type:
            raise serializers.ValidationError({'type': 'Create a new listing to change its type.'})
        return attrs


class FeedQuerySerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=['all', 'offer', 'request'], required=False)
    category = serializers.IntegerField(min_value=1, required=False)
    search = serializers.CharField(max_length=200, allow_blank=True, required=False)
    available = serializers.BooleanField(required=False)
    mine = serializers.BooleanField(required=False)
    ordering = serializers.ChoiceField(choices=['newest', 'oldest', 'nearest'], default='newest')
    latitude = serializers.FloatField(min_value=-90, max_value=90, required=False)
    longitude = serializers.FloatField(min_value=-180, max_value=180, required=False)
    radius_km = serializers.FloatField(min_value=0.1, max_value=100, required=False)

    def validate(self, attrs):
        lat, lon = attrs.get('latitude'), attrs.get('longitude')
        if (lat is None) != (lon is None):
            raise serializers.ValidationError('Provide both latitude and longitude.')
        for key in ('latitude', 'longitude', 'radius_km'):
            if key in attrs and not math.isfinite(attrs[key]):
                raise serializers.ValidationError({key: 'Use a finite number.'})
        if (attrs.get('radius_km') is not None or attrs['ordering'] == 'nearest') and lat is None:
            raise serializers.ValidationError('Distance filtering requires latitude and longitude.')
        return attrs


class ActivitySerializer(serializers.ModelSerializer):
    actor = PublicUserSerializer(read_only=True)

    class Meta:
        model = Activity
        fields = ('id', 'actor', 'type', 'listing', 'item_title', 'description', 'created_at')
