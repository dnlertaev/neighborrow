from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsVerifiedResident(BasePermission):
    message = 'Confirm your residential complex before using listings.'

    def has_permission(self, request, view):
        return bool(request.user.is_authenticated and request.user.is_resident_verified)


class IsOwnerOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS or request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        return request.method in SAFE_METHODS or obj.owner_id == request.user.pk
