from django.contrib.auth import authenticate, password_validation
from rest_framework import serializers
from .models import User

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'email', 'first_name', 'last_name', 'email_verified')
        read_only_fields = fields

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
        password_validation.validate_password(attrs['password'], candidate)
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_repeat')
        password = validated_data.pop('password')
        return User.objects.create_user(password=password, is_active=False, **validated_data)

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(trim_whitespace=False)

    def validate(self, attrs):
        user = authenticate(request=self.context.get('request'),
                            username=attrs['email'].lower(), password=attrs['password'])
        if not user:
            raise serializers.ValidationError('Invalid credentials or email is not verified.')
        attrs['user'] = user
        return attrs
