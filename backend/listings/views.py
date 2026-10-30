import re
from django.db import transaction
from django.db.models import Case, Exists, F, FloatField, IntegerField, OuterRef, Q, Value, When
from django.db.models.functions import ACos, Cos, Greatest, Least, Radians, Sin
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotAuthenticated, ValidationError
from rest_framework.response import Response
from .models import Activity, Category, Interest, Listing
from .permissions import IsOwnerOrReadOnly
from .serializers import (ActivitySerializer, CategorySerializer, FeedQuerySerializer,
                          ListingSerializer, PublicUserSerializer)


def add_activity(listing, actor, event, description, recipient=None):
    Activity.objects.create(recipient=recipient or actor, actor=actor, listing=listing,
                            type=event, item_title=listing.title, description=description)


class CategoryListView(generics.ListAPIView):
    permission_classes = (permissions.AllowAny,)
    serializer_class = CategorySerializer
    queryset = Category.objects.all()
    pagination_class = None


class ListingViewSet(viewsets.ModelViewSet):
    serializer_class = ListingSerializer
    permission_classes = (IsOwnerOrReadOnly,)
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']
    queryset = Listing.objects.select_related('owner', 'category').filter(owner__is_active=True)

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.user.is_authenticated:
            queryset = queryset.annotate(has_responded=Exists(Interest.objects.filter(
                listing_id=OuterRef('pk'), user=self.request.user)))
        if self.action != 'list':
            return queryset
        # A plain dict preserves absent booleans; HTML-style QueryDict would turn
        # an omitted `available` into False and hide all available listings.
        params = FeedQuerySerializer(data=self.request.query_params.dict())
        params.is_valid(raise_exception=True)
        data = params.validated_data
        if data.get('type') in ('offer', 'request'):
            queryset = queryset.filter(type=data['type'])
        if 'category' in data:
            queryset = queryset.filter(category_id=data['category'])
        if data.get('search'):
            queryset = queryset.filter(Q(title__icontains=data['search']) |
                                       Q(description__icontains=data['search']) |
                                       Q(category__name__icontains=data['search']))
        if 'available' in data:
            expired = Q(needed_until__lt=timezone.localdate())
            if data['available']:
                queryset = queryset.filter(available=True).exclude(expired)
            else:
                queryset = queryset.filter(Q(available=False) | expired)
        if data.get('mine'):
            if not self.request.user.is_authenticated:
                raise NotAuthenticated()
            queryset = queryset.filter(owner=self.request.user)
        if 'latitude' in data:
            # Spherical distance, computed by the database before filtering and pagination.
            lat, lon = Radians(Value(data['latitude'])), Radians(Value(data['longitude']))
            cosine = (Sin(lat) * Sin(Radians(F('latitude'))) +
                      Cos(lat) * Cos(Radians(F('latitude'))) * Cos(Radians(F('longitude')) - lon))
            distance = Value(6371.0088) * ACos(Least(Value(1.0), Greatest(Value(-1.0), cosine)))
            queryset = queryset.annotate(distance_km=Case(
                When(latitude__isnull=False, longitude__isnull=False, then=distance),
                default=Value(None), output_field=FloatField()))
        if 'radius_km' in data:
            queryset = queryset.filter(distance_km__lte=data['radius_km'])
        if data['ordering'] == 'nearest':
            return queryset.order_by(F('distance_km').asc(nulls_last=True), '-created_at', '-id')
        return queryset.order_by('created_at', 'id') if data['ordering'] == 'oldest' else queryset

    @transaction.atomic
    def perform_create(self, serializer):
        listing = serializer.save(owner=self.request.user)
        add_activity(listing, self.request.user, f'{listing.type}_created', 'Created a new listing')

    @transaction.atomic
    def perform_update(self, serializer):
        listing = serializer.save()
        add_activity(listing, self.request.user, 'listing_updated', 'Updated a listing')

    @transaction.atomic
    def perform_destroy(self, instance):
        add_activity(instance, self.request.user, 'listing_deleted', 'Deleted a listing')
        instance.delete()

    @action(detail=True, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def contacts(self, request, pk=None):
        listing = self.get_object()
        # Contacts are explicitly published per listing, never taken from a private profile.
        return Response({'owner': PublicUserSerializer(listing.owner).data,
                         'phone': listing.contact_phone, 'social_url': listing.contact_social})

    @action(detail=True, methods=['get'])
    def matches(self, request, pk=None):
        listing = self.get_object()
        candidates = self.get_queryset().none()
        if listing.available and (listing.needed_until is None or listing.needed_until >= timezone.localdate()):
            candidates = self.get_queryset().filter(category=listing.category, available=True).exclude(
                type=listing.type).exclude(owner=listing.owner).filter(
                Q(needed_until__isnull=True) | Q(needed_until__gte=timezone.localdate()))
            # Same category first; title words rank the shortlist. No automatic acceptance.
            words = sorted(set(re.findall(r'\w+', listing.title.lower())))[:10]
            score = Value(0, output_field=IntegerField())
            for word in words:
                if len(word) >= 3:
                    score = score + Case(When(title__icontains=word, then=Value(1)), default=Value(0))
            candidates = candidates.annotate(match_score=score).order_by('-match_score', '-created_at', '-id')
        page = self.paginate_queryset(candidates)
        return self.get_paginated_response(self.get_serializer(page, many=True).data)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    @transaction.atomic
    def interest(self, request, pk=None):
        listing = get_object_or_404(Listing.objects.select_for_update(), pk=pk, owner__is_active=True)
        if listing.owner_id == request.user.pk:
            raise ValidationError({'detail': 'You cannot respond to your own listing.'})
        if not listing.available or (listing.needed_until and listing.needed_until < timezone.localdate()):
            raise ValidationError({'detail': 'This listing is no longer available.'})
        interest, created = Interest.objects.get_or_create(listing=listing, user=request.user)
        if created:
            event = 'offer_requested' if listing.type == 'offer' else 'request_response'
            add_activity(listing, request.user, event, 'Responded to a listing')
            add_activity(listing, request.user, event, 'A neighbor responded to your listing', listing.owner)
        return Response({'id': interest.pk, 'listing': listing.pk, 'created': created},
                        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class ActivityListView(generics.ListAPIView):
    serializer_class = ActivitySerializer

    def get_queryset(self):
        return Activity.objects.filter(recipient=self.request.user).select_related('actor', 'listing')
