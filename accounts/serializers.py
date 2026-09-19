from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import User


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'password', 'role', 'roll_number', 'phone')

    def validate_role(self, value):
        # Issuer accounts are provisioned by staff (see issuers app), not self-registration,
        # so anyone signing up publicly can only ever become a STUDENT.
        if value != User.Role.STUDENT:
            raise serializers.ValidationError('Issuer accounts must be created by an existing issuer admin.')
        return value

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class UserSerializer(serializers.ModelSerializer):
    issuer_type = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'role', 'roll_number', 'phone', 'issuer_type')
        read_only_fields = ('role', 'issuer_type')

    def get_issuer_type(self, obj):
        membership = obj.issuer_memberships.first() if obj.is_issuer else None
        return membership.issuer_type if membership else None
