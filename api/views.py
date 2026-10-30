from rest_framework import exceptions
from rest_framework.response import Response
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView

from core import throttle
from core.security import client_ip

LIMIT, WINDOW = 5, 15 * 60


class StandingTokenSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        if not self.user.in_good_standing:  # pending / suspended / rejected accounts get no token
            raise exceptions.AuthenticationFailed('No active account found with the given credentials.')
        return data


class ThrottledTokenObtainPairView(TokenObtainPairView):
    """JWT login with the same brute-force protection as the web login."""
    serializer_class = StandingTokenSerializer

    def post(self, request, *args, **kwargs):
        username = str(request.data.get('username', ''))
        ip = client_ip(request) or 'unknown'
        if (throttle.is_limited('login_user', username, LIMIT, WINDOW)
                or throttle.is_limited('login_ip', ip, 4 * LIMIT, WINDOW)):
            return Response({'detail': 'Too many failed attempts. Try again later.'}, status=429)
        try:
            response = super().post(request, *args, **kwargs)
        except exceptions.APIException:
            throttle.record('login_user', username)
            throttle.record('login_ip', ip)
            raise
        throttle.reset('login_user', username)
        return response
