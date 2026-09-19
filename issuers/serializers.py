from rest_framework import serializers

from .models import Issuer


class IssuerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Issuer
        fields = ('id', 'name', 'issuer_type')
