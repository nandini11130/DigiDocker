from rest_framework.permissions import BasePermission


class IsIssuerStaff(BasePermission):
    message = 'Only issuer staff can issue documents.'

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_issuer)


class IsDocumentOwnerOrIssuingStaff(BasePermission):
    message = 'You do not have access to this document.'

    def has_object_permission(self, request, view, obj):
        if obj.owner_id == request.user.id:
            return True
        if obj.issuer_id and request.user.is_issuer:
            return obj.issuer.staff.filter(id=request.user.id).exists()
        return False
