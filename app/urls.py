from django.urls import path, re_path

from app import views

urlpatterns = [
    path("recipients/", views.RecipientList.as_view(), name="recipients-list"),
    re_path(
        r"^recipients/(?P<recipient_id>\d+)",
        views.RecipientDetail.as_view(),
        name="recipients-detail",
    ),
    path(
        "transfers/<int:transfer_id>",
        views.FileTransferDetails.as_view(),
        name="transfer-details",
    ),
    path(
        "transfers/<int:transfer_id>/form",
        views.FileTransferDetails.as_view(),
        name="transfer-form",
    ),
    path(
        "transfers/<int:transfer_id>/complete",
        views.FileTransferDetails.as_view(),
        name="transfer-complete",
    ),
    path(
        "transfers/<int:transfer_id>/recipients/<int:recipient_id>",
        views.FileTransferRecipientDetails.as_view(),
        name="transfer-recipient-details",
    ),
    path("transfers/", views.FileTransferList.as_view(), name="transfers-list"),
    path("user/<str:action>", views.UserView.as_view(), name="signup"),
]
