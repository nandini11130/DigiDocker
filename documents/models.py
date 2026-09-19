import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class Document(models.Model):
    """A document owned by a student, encrypted at rest with AES-256-GCM.

    status:
    - VERIFIED: an Issuer signed this exact file hash with its own RSA key
      (issued directly to the student, or a PENDING request the issuer
      approved after checking it - self-uploads never auto-verify).
    - UNVERIFIED: stored securely for the student's own use. No request is
      in flight - still perfectly safe, just not shareable as "verified".
    - PENDING: the student asked a specific Issuer (e.g. their college) to
      check and sign this document (e.g. a marksheet the college never issued
      through this platform directly). This is the ONE place a human makes a
      judgment call - but it's the authoritative institution reviewing its own
      record, not a platform admin rubber-stamping arbitrary uploads.
    """

    class DocType(models.TextChoices):
        AADHAAR = 'AADHAAR', 'Aadhaar Card'
        MARKSHEET = 'MARKSHEET', 'Marksheet'
        DEGREE = 'DEGREE', 'Degree Certificate'
        CERTIFICATE = 'CERTIFICATE', 'Other Certificate'
        OTHER = 'OTHER', 'Other'

    class Status(models.TextChoices):
        VERIFIED = 'VERIFIED', 'Verified'
        UNVERIFIED = 'UNVERIFIED', 'Unverified'
        PENDING = 'PENDING', 'Pending Verification'

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='documents', on_delete=models.CASCADE)
    issuer = models.ForeignKey(
        'issuers.Issuer', null=True, blank=True, on_delete=models.SET_NULL, related_name='documents',
    )
    doc_type = models.CharField(max_length=20, choices=DocType.choices)
    title = models.CharField(max_length=255)

    encrypted_file = models.FileField(upload_to='secure_docs/%Y/%m/')
    original_filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100, blank=True)

    # Envelope encryption: a random per-document AES-256 key encrypts the file
    # bytes, and that data key is itself AES-256-GCM encrypted with the server
    # master key, so the master key never touches file bytes directly.
    file_nonce = models.BinaryField()
    data_key_nonce = models.BinaryField()
    data_key_ciphertext = models.BinaryField()

    file_sha256 = models.CharField(max_length=64, db_index=True)
    signature = models.BinaryField(null=True, blank=True)

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.UNVERIFIED)
    issued_at = models.DateTimeField(null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    # Set when the student requests verification (status becomes PENDING) and
    # cleared/explained by the issuer's decision.
    requested_at = models.DateTimeField(null=True, blank=True)
    review_note = models.CharField(max_length=500, blank=True)

    # Rotatable token for a read-only "verified document" link a student can
    # hand to a recruiter/placement cell instead of carrying paper copies.
    # The token alone does NOT grant access - see is_share_active(): it must
    # also be within its expiry window and view budget, both reset every time
    # the student (re)generates a link, so an old leaked link stops working.
    share_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    share_expires_at = models.DateTimeField(null=True, blank=True)
    share_max_views = models.PositiveIntegerField(default=20)
    share_view_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f'{self.title} ({self.owner})'

    def is_share_active(self) -> bool:
        if not self.share_expires_at or timezone.now() > self.share_expires_at:
            return False
        return self.share_view_count < self.share_max_views

    def is_previewable(self) -> bool:
        """Aadhaar content is never shown publicly - only its verified status is.
        Marksheets/degrees/certificates can be previewed so a recruiter can read them."""
        return self.doc_type != self.DocType.AADHAAR
