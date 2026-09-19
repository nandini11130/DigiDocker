from django.contrib import admin

from .models import Document


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    """Read-only: status is derived automatically from issuer signature
    matching (see documents/views.py). Intentionally no approve/reject action."""

    list_display = ('title', 'doc_type', 'owner', 'issuer', 'status', 'uploaded_at')
    list_filter = ('doc_type', 'status', 'issuer')
    search_fields = ('title', 'owner__username', 'owner__roll_number')
    readonly_fields = [f.name for f in Document._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
