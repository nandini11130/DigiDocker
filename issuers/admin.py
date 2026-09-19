from django.contrib import admin

from .models import Issuer


@admin.register(Issuer)
class IssuerAdmin(admin.ModelAdmin):
    """Institutional onboarding only. Creating an Issuer here auto-generates its
    RSA keypair; there is intentionally no per-document approval UI anywhere."""

    list_display = ('name', 'issuer_type', 'created_at')
    filter_horizontal = ('staff',)
    readonly_fields = ('public_key_pem', 'created_at')
    exclude = ('private_key_nonce', 'private_key_ciphertext')

    def save_model(self, request, obj, form, change):
        if not change:
            created = Issuer.create_with_keypair(name=obj.name, issuer_type=obj.issuer_type)
            obj.pk = created.pk
            obj.public_key_pem = created.public_key_pem
            obj.private_key_nonce = created.private_key_nonce
            obj.private_key_ciphertext = created.private_key_ciphertext
        super().save_model(request, obj, form, change)
