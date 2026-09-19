from rest_framework import serializers

from issuers.models import Issuer

from .models import Document


class DocumentSerializer(serializers.ModelSerializer):
    issuer_name = serializers.CharField(source='issuer.name', read_only=True, default=None)
    owner_username = serializers.CharField(source='owner.username', read_only=True)

    class Meta:
        model = Document
        fields = (
            'id', 'doc_type', 'title', 'status', 'issuer', 'issuer_name',
            'owner_username', 'original_filename', 'file_sha256',
            'uploaded_at', 'issued_at', 'share_token', 'share_expires_at',
            'share_max_views', 'share_view_count', 'requested_at', 'review_note',
        )
        read_only_fields = fields


class IssueDocumentSerializer(serializers.Serializer):
    file = serializers.FileField()
    doc_type = serializers.ChoiceField(choices=Document.DocType.choices)
    title = serializers.CharField(max_length=255)
    student_roll_number = serializers.CharField(max_length=50)


class SelfUploadDocumentSerializer(serializers.Serializer):
    file = serializers.FileField()
    doc_type = serializers.ChoiceField(choices=Document.DocType.choices)
    title = serializers.CharField(max_length=255)


class RequestVerificationSerializer(serializers.Serializer):
    issuer = serializers.PrimaryKeyRelatedField(queryset=Issuer.objects.all())


class ReviewDecisionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=['approve', 'reject'])
    note = serializers.CharField(max_length=500, required=False, allow_blank=True)
