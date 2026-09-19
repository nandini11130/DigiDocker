import io
import uuid
from datetime import timedelta

import qrcode
from django.conf import settings
from django.core.files.base import ContentFile
from django.db.models import F
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User

from .models import Document
from .permissions import IsDocumentOwnerOrIssuingStaff, IsIssuerStaff
from .serializers import (
    DocumentSerializer,
    IssueDocumentSerializer,
    RequestVerificationSerializer,
    ReviewDecisionSerializer,
    SelfUploadDocumentSerializer,
)
from .services import decrypt_document_file, encrypt_file_for_storage


class DocumentListView(generics.ListAPIView):
    serializer_class = DocumentSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['doc_type', 'status']

    def get_queryset(self):
        user = self.request.user
        if user.is_issuer:
            return Document.objects.filter(issuer__staff=user).select_related('issuer', 'owner')
        return Document.objects.filter(owner=user).select_related('issuer', 'owner')


class IssueDocumentView(APIView):
    """Issuer staff issue a document to a student (e.g. college issues a
    marksheet, UIDAI-mock issues an Aadhaar). Signing the file hash with the
    issuer's own private key IS the verification — no separate admin review."""

    permission_classes = [permissions.IsAuthenticated, IsIssuerStaff]

    def post(self, request):
        serializer = IssueDocumentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        issuer = request.user.issuer_memberships.first()
        if issuer is None:
            raise PermissionDenied('Your account is not linked to any issuer.')
        if data['doc_type'] not in issuer.allowed_doc_types():
            raise ValidationError({
                'doc_type': f'{issuer.get_issuer_type_display()} issuers cannot issue this document type.',
            })

        try:
            student = User.objects.get(roll_number=data['student_roll_number'], role=User.Role.STUDENT)
        except User.DoesNotExist:
            raise ValidationError({'student_roll_number': 'No student found with this roll number.'})

        upload = data['file']
        if upload.size > settings.MAX_DOCUMENT_UPLOAD_BYTES:
            raise ValidationError({'file': 'File too large.'})
        raw_bytes = upload.read()

        enc = encrypt_file_for_storage(raw_bytes)
        signature = issuer.sign(enc['sha256'].encode('utf-8'))

        document = Document(
            owner=student,
            issuer=issuer,
            doc_type=data['doc_type'],
            title=data['title'],
            original_filename=upload.name,
            content_type=upload.content_type or '',
            file_nonce=enc['file_nonce'],
            data_key_nonce=enc['data_key_nonce'],
            data_key_ciphertext=enc['data_key_ciphertext'],
            file_sha256=enc['sha256'],
            signature=signature,
            status=Document.Status.VERIFIED,
            issued_at=timezone.now(),
        )
        document.encrypted_file.save(f'{uuid.uuid4()}.bin', ContentFile(enc['ciphertext']), save=False)
        document.save()

        return Response(DocumentSerializer(document).data, status=status.HTTP_201_CREATED)


class SelfUploadDocumentView(APIView):
    """A student uploads their own copy of a document. It always lands as
    UNVERIFIED - only the issuing institution can mark it VERIFIED, via the
    request-verification -> review flow below. No auto-verification on upload."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = SelfUploadDocumentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        upload = data['file']
        if upload.size > settings.MAX_DOCUMENT_UPLOAD_BYTES:
            raise ValidationError({'file': 'File too large.'})
        raw_bytes = upload.read()

        enc = encrypt_file_for_storage(raw_bytes)

        if Document.objects.filter(owner=request.user, file_sha256=enc['sha256']).exists():
            raise ValidationError({'file': 'You have already uploaded this exact document.'})

        document = Document(
            owner=request.user,
            doc_type=data['doc_type'],
            title=data['title'],
            original_filename=upload.name,
            content_type=upload.content_type or '',
            file_nonce=enc['file_nonce'],
            data_key_nonce=enc['data_key_nonce'],
            data_key_ciphertext=enc['data_key_ciphertext'],
            file_sha256=enc['sha256'],
            status=Document.Status.UNVERIFIED,
        )
        document.encrypted_file.save(f'{uuid.uuid4()}.bin', ContentFile(enc['ciphertext']), save=False)
        document.save()

        return Response(DocumentSerializer(document).data, status=status.HTTP_201_CREATED)


class RequestVerificationView(APIView):
    """A student asks a specific Issuer (e.g. their own college) to check and
    sign a document that didn't auto-verify on upload — typically because it
    was originally issued on paper/PDF outside this platform, so there's no
    prior signed copy to hash-match against. Moves status UNVERIFIED -> PENDING;
    the issuer decides via ReviewVerificationView below."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        document = get_object_or_404(Document, pk=pk, owner=request.user)
        if document.status != Document.Status.UNVERIFIED:
            raise ValidationError({'detail': 'Only unverified documents can have a verification request raised.'})

        serializer = RequestVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        issuer = serializer.validated_data['issuer']
        if document.doc_type not in issuer.allowed_doc_types():
            raise ValidationError({
                'issuer': f'{issuer.get_issuer_type_display()} issuers cannot verify this document type.',
            })

        document.issuer = issuer
        document.status = Document.Status.PENDING
        document.requested_at = timezone.now()
        document.review_note = ''
        document.save(update_fields=['issuer', 'status', 'requested_at', 'review_note'])
        return Response(DocumentSerializer(document).data)


class ReviewVerificationView(APIView):
    """The issuer staff who received a request approves (signs it, exactly like
    IssueDocumentView) or rejects it (back to UNVERIFIED, with a note explaining
    why). This is the one deliberate human-in-the-loop step in the whole system —
    but it's the authoritative institution reviewing its own record, not a
    platform admin approving arbitrary uploads."""

    permission_classes = [permissions.IsAuthenticated, IsIssuerStaff]

    def post(self, request, pk):
        document = get_object_or_404(Document, pk=pk, status=Document.Status.PENDING)
        issuer = request.user.issuer_memberships.first()
        if issuer is None or document.issuer_id != issuer.id:
            raise PermissionDenied('This request was not addressed to your institution.')

        serializer = ReviewDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action = serializer.validated_data['action']
        note = serializer.validated_data.get('note', '')

        if action == 'approve':
            document.signature = issuer.sign(document.file_sha256.encode('utf-8'))
            document.status = Document.Status.VERIFIED
            document.issued_at = timezone.now()
            document.review_note = note
            document.save(update_fields=['signature', 'status', 'issued_at', 'review_note'])
        else:
            document.status = Document.Status.UNVERIFIED
            document.issuer = None
            document.review_note = note or 'Rejected by issuer.'
            document.save(update_fields=['status', 'issuer', 'review_note'])

        return Response(DocumentSerializer(document).data)


class DocumentDownloadView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsDocumentOwnerOrIssuingStaff]

    def get(self, request, pk):
        document = get_object_or_404(Document, pk=pk)
        self.check_object_permissions(request, document)
        raw_bytes = decrypt_document_file(document)
        return FileResponse(
            ContentFile(raw_bytes),
            as_attachment=True,
            filename=document.original_filename or f'document-{document.pk}',
        )


class RegenerateShareLinkView(APIView):
    """Owner (re)activates sharing: rotates the token, and resets the expiry
    window + view budget so a previously leaked link stops working immediately.
    Nothing is shareable until this has been called at least once."""

    permission_classes = [permissions.IsAuthenticated]
    MAX_HOURS = 168  # 7 days

    def post(self, request, pk):
        document = get_object_or_404(Document, pk=pk, owner=request.user)
        hours = min(int(request.data.get('hours', 48) or 48), self.MAX_HOURS)
        document.share_token = uuid.uuid4()
        document.share_expires_at = timezone.now() + timedelta(hours=hours)
        document.share_view_count = 0
        document.save(update_fields=['share_token', 'share_expires_at', 'share_view_count'])
        return Response(DocumentSerializer(document).data)


class ShareQRCodeView(APIView):
    """QR code for the public verify link, so a recruiter can scan it on the spot."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        document = get_object_or_404(Document, pk=pk, owner=request.user)
        link = request.build_absolute_uri(f'/verify/{document.share_token}/')
        img = qrcode.make(link)
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return HttpResponse(buf.getvalue(), content_type='image/png')


class PublicVerifyView(APIView):
    """What a recruiter/placement cell sees via the shared link or QR code.
    Aadhaar never exposes its content here, only its verified status - the
    actual file is only reachable through PreviewFileView, and only for
    non-Aadhaar docs, and only while the link is still active (see below)."""

    permission_classes = [permissions.AllowAny]

    def get(self, request, token):
        document = get_object_or_404(Document, share_token=token)
        if not document.is_share_active():
            raise NotFound('This verification link is invalid, expired, or has been revoked.')
        payload = {
            'title': document.title,
            'doc_type': document.get_doc_type_display(),
            'status': document.status,
            'issuer': document.issuer.name if document.issuer else None,
            'owner_name': document.owner.get_full_name() or document.owner.username,
            'issued_at': document.issued_at,
            'uploaded_at': document.uploaded_at,
            'expires_at': document.share_expires_at,
            'views_remaining': max(document.share_max_views - document.share_view_count, 0),
            'preview_available': document.status == Document.Status.VERIFIED and document.is_previewable(),
        }
        return Response(payload)


class PreviewFileView(APIView):
    """Streams the decrypted file inline (view-only, not as_attachment) for a
    recruiter to actually read the marks/certificate. Each successful preview
    consumes one "view" from the link's budget - independent of how many times
    the metadata endpoint above was hit. Aadhaar documents are never served
    here, by design, regardless of link validity."""

    permission_classes = [permissions.AllowAny]

    def get(self, request, token):
        document = get_object_or_404(Document, share_token=token)
        if not document.is_share_active():
            raise NotFound('This verification link is invalid, expired, or has been revoked.')
        if document.status != Document.Status.VERIFIED or not document.is_previewable():
            raise PermissionDenied('This document cannot be previewed publicly.')
        Document.objects.filter(pk=document.pk).update(share_view_count=F('share_view_count') + 1)
        raw_bytes = decrypt_document_file(document)
        return FileResponse(
            ContentFile(raw_bytes), content_type=document.content_type or 'application/octet-stream',
        )
