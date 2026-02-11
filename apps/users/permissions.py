from rest_framework import permissions

class IsAdminUser(permissions.BasePermission):
    """
    Permite el acceso solo a usuarios con rol 'admin'.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.rol == 'admin')

class IsSucursalUser(permissions.BasePermission):
    """
    Permite el acceso a vendedores o admins.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)