from django.urls import path

from .views import (
    DocumentDownloadView,
    DocumentListView,
    IssueDocumentView,
    PreviewFileView,
    PublicVerifyView,
    RegenerateShareLinkView,
    RequestVerificationView,
    ReviewVerificationView,
    SelfUploadDocumentView,
    ShareQRCodeView,
)

urlpatterns = [
    path('', DocumentListView.as_view(), name='document-list'),
    path('issue/', IssueDocumentView.as_view(), name='document-issue'),
    path('upload/', SelfUploadDocumentView.as_view(), name='document-self-upload'),
    path('<int:pk>/download/', DocumentDownloadView.as_view(), name='document-download'),
    path('<int:pk>/request-verification/', RequestVerificationView.as_view(), name='document-request-verification'),
    path('<int:pk>/review/', ReviewVerificationView.as_view(), name='document-review'),
    path('<int:pk>/share/regenerate/', RegenerateShareLinkView.as_view(), name='document-share-regenerate'),
    path('<int:pk>/share/qr/', ShareQRCodeView.as_view(), name='document-share-qr'),
    path('verify/<uuid:token>/', PublicVerifyView.as_view(), name='document-verify'),
    path('verify/<uuid:token>/preview/', PreviewFileView.as_view(), name='document-preview'),
]
