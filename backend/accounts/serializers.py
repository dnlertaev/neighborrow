from django.contrib.auth import authenticate, password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from rest_framework import serializers
from rest_framework_simplejwt.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.utils import get_md5_hash_password
from .models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'email', 'first_name', 'last_name', 'address', 'phone', 'social_url')
        read_only_fields = ('id', 'email')

    def validate_social_url(self, value):
        if value and not value.startswith(('https://', 'http://')):
            raise serializers.ValidationError('Use an HTTP or HTTPS link.')
        return value


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    password_repeat = serializers.CharField(write_only=True, trim_whitespace=False)

    class Meta:
        model = User
        fields = ('email', 'password', 'password_repeat', 'first_name', 'last_name')

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('This email is already registered.')
        return value

    def validate(self, attrs):
        if attrs['password'] != attrs['password_repeat']:
            raise serializers.ValidationError({'password_repeat': 'Passwords do not match.'})
        candidate = User(email=attrs['email'], first_name=attrs.get('first_name', ''),
                         last_name=attrs.get('last_name', ''))
        try:
            password_validation.validate_password(attrs['password'], candidate)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({'password': exc.messages})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_repeat')
        password = validated_data.pop('password')
        try:
            with transaction.atomic():
                return User.objects.create_user(password=password, **validated_data)
        except IntegrityError:
            raise serializers.ValidationError({'email': 'This email is already registered.'})


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        user = authenticate(request=self.context.get('request'),
                            username=attrs['email'].strip().lower(), password=attrs['password'])
        if not user:
            raise serializers.ValidationError('Invalid email or password.')
        attrs['user'] = user
        return attrs


class RefreshSerializer(TokenRefreshSerializer):
    def validate(self, attrs):
        token = RefreshToken(attrs['refresh'])
        user = User.objects.filter(pk=token.get(api_settings.USER_ID_CLAIM), is_active=True).first()
        if not user or token.get(api_settings.REVOKE_TOKEN_CLAIM) != get_md5_hash_password(user.password):
            raise AuthenticationFailed('This session is no longer valid.', code='session_revoked')
        return super().validate(attrs)


class PasswordConfirmationSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_current_password(self, value):
        if not self.context['request'].user.check_password(value):
            raise serializers.ValidationError('Incorrect current password.')
        return value


class PasswordChangeSerializer(PasswordConfirmationSerializer):
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)
    new_password_repeat = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_repeat']:
            raise serializers.ValidationError({'new_password_repeat': 'Passwords do not match.'})
        try:
            password_validation.validate_password(attrs['new_password'], self.context['request'].user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({'new_password': exc.messages})
        return attrs


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(trim_whitespace=False)
