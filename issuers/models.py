from django.conf import settings
from django.db import models

from common.crypto import aes_decrypt, aes_encrypt, generate_rsa_keypair, get_master_key, sign_bytes


class Issuer(models.Model):
    """A verifying authority (a college, or a UIDAI-mock for Aadhaar) that can
    issue documents which are auto-verified via digital signature — no human
    admin ever approves an individual document.

    Onboarding a new Issuer is a one-time institutional setup step done via
    Django admin by a platform operator; it is NOT per-document approval.
    """

    class IssuerType(models.TextChoices):
        COLLEGE = 'COLLEGE', 'College (identity / admission verification)'
        UNIVERSITY = 'UNIVERSITY', 'University (marksheets & degrees)'
        GOVERNMENT = 'GOVERNMENT', 'Government (e.g. UIDAI-mock)'
        OTHER = 'OTHER', 'Other'

    # Which Document.DocType values (see documents/models.py) each issuer type may
    # issue. Mirrors how it actually works in India: the affiliating COLLEGE
    # verifies a student's identity/Aadhaar at admission, while the affiliated
    # UNIVERSITY is the body that awards marksheets/degrees - a college has no
    # business signing a degree, and a university has no business vouching for
    # someone's Aadhaar. Kept as plain strings (not a Document import) to avoid
    # coupling this app to the documents app.
    ALLOWED_DOC_TYPES = {
        'COLLEGE': {'AADHAAR', 'CERTIFICATE', 'OTHER'},
        'UNIVERSITY': {'MARKSHEET', 'DEGREE', 'CERTIFICATE', 'OTHER'},
        'GOVERNMENT': {'AADHAAR', 'OTHER'},
        'OTHER': {'AADHAAR', 'MARKSHEET', 'DEGREE', 'CERTIFICATE', 'OTHER'},
    }

    name = models.CharField(max_length=255, unique=True)
    issuer_type = models.CharField(max_length=20, choices=IssuerType.choices, default=IssuerType.COLLEGE)
    public_key_pem = models.TextField(editable=False)
    private_key_nonce = models.BinaryField(editable=False)
    private_key_ciphertext = models.BinaryField(editable=False)
    staff = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name='issuer_memberships', blank=True,
        limit_choices_to={'role': 'ISSUER'},
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    def allowed_doc_types(self) -> set:
        return self.ALLOWED_DOC_TYPES.get(self.issuer_type, set())

    @classmethod
    def create_with_keypair(cls, *, name, issuer_type):
        private_pem, public_pem = generate_rsa_keypair()
        nonce, ciphertext = aes_encrypt(get_master_key(), private_pem)
        return cls.objects.create(
            name=name,
            issuer_type=issuer_type,
            public_key_pem=public_pem.decode('utf-8'),
            private_key_nonce=nonce,
            private_key_ciphertext=ciphertext,
        )

    def _private_key_pem(self) -> bytes:
        return aes_decrypt(get_master_key(), bytes(self.private_key_nonce), bytes(self.private_key_ciphertext))

    def sign(self, data: bytes) -> bytes:
        """Sign a document hash with this issuer's private key. This signature IS
        the verification — no separate manual approval step exists anywhere."""
        return sign_bytes(self._private_key_pem(), data)
