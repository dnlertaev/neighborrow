from django.db import transaction
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.views import TokenRefreshView
from .models import ResidentialComplex, User
from listings.models import Listing
from .serializers import (LoginSerializer, LogoutSerializer, RegisterSerializer, UserSerializer,
                          PasswordConfirmationSerializer, PasswordChangeSerializer, RefreshSerializer,
                          ResidentialComplexSerializer, VerifyResidenceSerializer)


class AuthThrottleMixin:
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = 'auth'


class RegisterView(AuthThrottleMixin, generics.CreateAPIView):
    permission_classes = (permissions.AllowAny,)
    authentication_classes = ()
    serializer_class = RegisterSerializer


class LoginView(AuthThrottleMixin, APIView):
    permission_classes = (permissions.AllowAny,)
    authentication_classes = ()

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        refresh = RefreshToken.for_user(user)
        return Response({'access': str(refresh.access_token), 'refresh': str(refresh),
                         'user': UserSerializer(user).data})


class RefreshView(AuthThrottleMixin, TokenRefreshView):
    serializer_class = RefreshSerializer


class ResidentialComplexListView(generics.ListAPIView):
    serializer_class = ResidentialComplexSerializer
    pagination_class = None
    queryset = ResidentialComplex.objects.filter(is_active=True)


class VerifyResidenceView(APIView):
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = 'residence_verify'

    @transaction.atomic
    def post(self, request):
        user = User.objects.select_for_update().get(pk=request.user.pk)
        serializer = VerifyResidenceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        complex_id = serializer.validated_data['residential_complex']
        complex = ResidentialComplex.objects.filter(pk=complex_id, is_active=True).first()
        if complex is None:
            raise ValidationError({'residential_complex': 'Choose a listed residential complex.'})
        if user.is_resident_verified and user.residential_complex_id == complex.pk:
            raise ValidationError({'residential_complex': 'This residential complex is already confirmed.'})
        if not complex.check_code(serializer.validated_data['code']):
            raise ValidationError({'code': 'Incorrect code for the selected residential complex.'})
        verified_at = timezone.now()
        if user.is_resident_verified:
            Listing.objects.filter(owner=user, archived_at__isnull=True).update(archived_at=verified_at)
        updated = User.objects.filter(pk=user.pk, residential_complex_id=user.residential_complex_id,
            residential_verified_at=user.residential_verified_at).update(
            residential_complex=complex, residential_verified_at=verified_at)
        if not updated:
            raise ValidationError({'detail': 'Residential complex changed during verification. Try again.'})
        request.user.refresh_from_db()
        return Response(UserSerializer(request.user).data)


class LogoutView(APIView):
    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            token = RefreshToken(serializer.validated_data['refresh'])
            if str(token[api_settings.USER_ID_CLAIM]) != str(request.user.pk):
                return Response({'detail': 'Invalid refresh token.'}, status=400)
            token.blacklist()
        except (KeyError, TokenError):
            return Response({'detail': 'Invalid refresh token.'}, status=400)
        return Response(status=status.HTTP_204_NO_CONTENT)


def revoke_refresh_tokens(user):
    for token in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=token)


class MeView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = UserSerializer
    http_method_names = ['get', 'patch', 'delete', 'head', 'options']

    def get_object(self):
        return self.request.user

    def destroy(self, request, *args, **kwargs):
        serializer = PasswordConfirmationSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            revoke_refresh_tokens(request.user)
            request.user.delete()
        return Response(status=204)


class PasswordChangeView(AuthThrottleMixin, APIView):
    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            request.user.set_password(serializer.validated_data['new_password'])
            request.user.save(update_fields=['password'])
            revoke_refresh_tokens(request.user)
        return Response({'detail': 'Password changed. Sign in again.'})
