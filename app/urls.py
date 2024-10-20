from django.urls import path, re_path, include
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework import permissions, routers

from app import views


schema_view = get_schema_view(
    openapi.Info(
        title="Snippets API",
        default_version="v1",
        description="Test description",
        terms_of_service="https://www.google.com/policies/terms/",
        contact=openapi.Contact(email="contact@snippets.local"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

router = routers.DefaultRouter()

router.register(r"user", views.UserViewSet, basename="user")

urlpatterns = [
    path("recipients/", views.RecipientList.as_view(), name="recipients-list"),
    path(
        "recipients/<int:recipient_id>/<str:action>",
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
    path(
        "swagger/",
        schema_view.with_ui("swagger", cache_timeout=0),
        name="schema-swagger-ui",
    ),
    # path("user", include(router.urls)),
    path("api-auth/", include("rest_framework.urls", namespace="rest_framework")),
    path("signin", views.signin, name="signin"),
    path("signout", views.signout, name="signout"),
]

urlpatterns += router.urls
