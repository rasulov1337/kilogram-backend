from django.urls import path, re_path

from app import views

urlpatterns = [
    path('recipients/', views.RecipientList.as_view(), name='recipients-list'),
    re_path(r'^recipients/(?P<recipient_id>\d+)', views.RecipientDetail.as_view(), name='recipients-detail'),

    # re_path(r'^user/', views.CreateUserView.as_view(), name='sign-up'),

    path('transfers/', views.FileTransferList.as_view(), name='transfers-list'),
    re_path(r'transfers/(?P<transfer_id>\d+)', views.FileTransferDetails.as_view(), name='transfers-details'),

]
