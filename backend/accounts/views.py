from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.encoding import force_bytes
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import LoginSerializer, RegisterSerializer, UserSerializer
from .tokens import email_verification_token

User = get_user_model()

class RegisterView(generics.CreateAPIView):
    permission_classes = (permissions.AllowAny,)
    serializer_class = RegisterSerializer

    def perform_create(self, serializer):
        user = serializer.save()
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = email_verification_token.make_token(user)
        link = f'{settings.FRONTEND_URL}/verify-email?uid={uid}&token={token}'
        try:
            send_mail('Verify your Neighborrow email',
                      f'Confirm your email within 24 hours: {link}',
                      settings.DEFAULT_FROM_EMAIL, [user.email])
        except Exception:
            user.delete()
            raise

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        return Response({'detail': 'Check your email to verify your account.'}, status=response.status_code)

class VerifyEmailView(APIView):
    permission_classes = (permissions.AllowAny,)

    def post(self, request):
        try:
            uid = force_str(urlsafe_base64_decode(request.data.get('uid', '')))
            user = User.objects.get(pk=uid, email_verified=False)
        except (ValueError, TypeError, OverflowError, User.DoesNotExist):
            return Response({'detail': 'Invalid or expired verification link.'}, status=400)
        if not email_verification_token.check_token(user, request.data.get('token', '')):
            return Response({'detail': 'Invalid or expired verification link.'}, status=400)
        user.email_verified = True
        user.is_active = True
        user.save(update_fields=['email_verified', 'is_active'])
        return Response({'detail': 'Email verified. You can now sign in.'})

class LoginView(APIView):
    permission_classes = (permissions.AllowAny,)

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        refresh = RefreshToken.for_user(user)
        return Response({'access': str(refresh.access_token), 'refresh': str(refresh),
                         'user': UserSerializer(user).data})

class LogoutView(APIView):
    def post(self, request):
        try:
            RefreshToken(request.data['refresh']).blacklist()
        except (KeyError, TokenError):
            return Response({'detail': 'Invalid refresh token.'}, status=400)
        return Response(status=status.HTTP_204_NO_CONTENT)

class MeView(generics.RetrieveAPIView):
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user
