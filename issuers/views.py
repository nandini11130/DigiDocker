from rest_framework import generics, permissions

from .models import Issuer
from .serializers import IssuerSerializer


class IssuerListView(generics.ListAPIView):
    """Public-ish list so a student can pick which institution to send a
    verification request to."""
    queryset = Issuer.objects.all().order_by('name')
    serializer_class = IssuerSerializer
    permission_classes = [permissions.IsAuthenticated]
