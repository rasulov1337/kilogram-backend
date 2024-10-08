from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.db.models import Q
from django.http import Http404
from django.shortcuts import render, get_object_or_404, redirect
from django.db import connection
from django.utils import timezone
from minio import Minio
from rest_framework import status, permissions
from rest_framework.decorators import api_view
from rest_framework.generics import CreateAPIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from app.models import Recipient, FileTransfer

from app.models import Recipient, FileTransfer, FileTransferRecipient
from app.serializers import RecipientSerializer, UserSerializer, FileTransferSerializer, FileTransferRecipientSerializer
from rip import settings


class UserSingleton:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            try:
                cls._instance = User.objects.get(id=1)
            except ObjectDoesNotExist:
                cls._instance = None
        return cls._instance


class MinioClient:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = Minio(endpoint=settings.AWS_S3_ENDPOINT_URL,
                                  access_key=settings.AWS_ACCESS_KEY_ID,
                                  secret_key=settings.AWS_SECRET_ACCESS_KEY,
                                  secure=settings.MINIO_USE_SSL)
        return cls._instance


def load_img(recipient: Recipient, img: InMemoryUploadedFile):
    client = MinioClient()

    img_obj_name = "%i.png" % recipient.id

    if not img:
        raise Exception("Не указан путь к изображению")

    client.put_object(bucket_name=settings.AWS_STORAGE_BUCKET_NAME,
                      object_name=img_obj_name,
                      data=img,
                      length=img.size)
    url_to_img = 'http://localhost:9000/rip-images/%s' % img_obj_name

    return url_to_img


def delete_img(img_name: str):
    client = MinioClient()
    client.remove_object(settings.AWS_STORAGE_BUCKET_NAME, img_name)


class RecipientList(APIView):
    model_class = Recipient
    serializer_class = RecipientSerializer

    # Get list of all recipients
    def get(self, request):
        user = UserSingleton.get_instance()
        draft = FileTransfer.objects.get_draft(user.id)

        recipients = self.model_class.objects.all()
        serializer = self.serializer_class(recipients, many=True)
        data = serializer.data
        data.append({'draft_id': draft.id if draft else None})
        return Response(data)

    # Create a new recipient
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RecipientDetail(APIView):
    model_class = Recipient
    serializer_class = RecipientSerializer

    def get(self, request, recipient_id):
        recipient = get_object_or_404(self.model_class, id=recipient_id)
        serializer = self.serializer_class(recipient)
        return Response(serializer.data)

    def put(self, request, recipient_id):
        recipient = get_object_or_404(self.model_class, id=recipient_id)
        serializer = self.serializer_class(recipient, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, recipient_id):
        recipient = get_object_or_404(self.model_class, id=recipient_id)
        if recipient.status == 'D':
            return Response({"error": "User already deleted"}, status.HTTP_400_BAD_REQUEST)
        try:
            delete_img(recipient.avatar.split('/')[-1])
        except Exception as e:
            return Response({"error": str(e)}, status.HTTP_500_INTERNAL_SERVER_ERROR)
        recipient.status = 'D'
        recipient.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def post(self, request: Request, recipient_id):
        if request.path.endswith('/image/'):
            return self.image(request, recipient_id)
        elif request.path.endswith('/draft/'):
            return self.draft(request, recipient_id)
        raise Http404

    def draft(self, request, recipient_id):
        if not UserSingleton.get_instance(user_id=1).is_authenticated:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        recipient = get_object_or_404(Recipient, id=recipient_id)
        draft_transfer = FileTransfer.objects.get_draft(UserSingleton.get_instance(user_id=1).id)
        if not draft_transfer:
            draft_transfer = FileTransfer.objects.create(status='DRF', sender=UserSingleton.get_instance(user_id=1))
            draft_transfer.save()

        if draft_transfer.recipients.contains(recipient):
            return Response(data={"error": "User already added"}, status=status.HTTP_400_BAD_REQUEST)

        draft_transfer.recipients.add(recipient, through_defaults={})
        draft_transfer.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def image(self, request, recipient_id):
        avatar = request.FILES.get('avatar', None)

        if not avatar:
            return Response({"error": "Файл с изображением не загружен"}, status=status.HTTP_400_BAD_REQUEST)

        recipient = get_object_or_404(Recipient, id=recipient_id)

        try:
            # The image is replaced automatically
            # if recipient.avatar:
            #     delete_img(recipient.avatar.split('/')[-1])

            avatar_url = load_img(recipient, avatar)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        recipient.avatar = avatar_url
        recipient.save()

        return Response({"message": "Изображение обновлено",
                         "avatar": avatar_url},
                        status=status.HTTP_200_OK)


@api_view(['PUT'])
def edit(request):
    pass


@api_view(['POST'])
def signin(request):
    if UserSingleton.get_instance(user_id=1).is_authenticated:
        return Response({
            'error': 'Already authenticated'
        }, status.HTTP_400_BAD_REQUEST)

    username = request.data.get("username")
    password = request.data.get("password")
    user = authenticate(username=username, password=password)
    if not user:
        return Response({
            "error": "Wrong credentials!"
        }, status.HTTP_401_UNAUTHORIZED)

    return Response({
        "status": "Success"
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
def signout(request):
    pass


class FileTransferList(APIView):
    model_class = FileTransfer
    serializer_class = FileTransferSerializer

    def get(self, request):
        transfers = self.model_class.objects.filter(~(Q(status='DRF') | Q(status='DEL')))
        serializer = self.serializer_class(transfers, many=True)
        return Response(serializer.data)


class FileTransferDetails(APIView):
    model_class = FileTransfer
    serializer_class = FileTransferSerializer

    def get(self, request, transfer_id):
        transfer = get_object_or_404(self.model_class, id=transfer_id)
        serializer = self.serializer_class(transfer)
        return Response(serializer.data)

    def put(self, request: Request, transfer_id):
        if request.path.endswith('/edit'):
            return self.edit(request, transfer_id)
        elif request.path.endswith('/form'):
            return self.form(request, transfer_id)
        elif request.path.endswith('/complete'):
            return self.complete(request, transfer_id)
        raise Http404

    def edit(self, request: Request, transfer_id: int):
        transfer = get_object_or_404(self.model_class, id=transfer_id)
        serializer = self.serializer_class(transfer, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def form(self, request: Request, transfer_id: int):
        transfer: FileTransfer = get_object_or_404(self.model_class, id=transfer_id)
        empty_fields = []
        if not transfer.recipients.count():
            empty_fields.append('recipients field is empty')

        if not transfer.file:
            empty_fields.append('no files selected for transfer')

        if empty_fields:
            return Response({'error': empty_fields}, status=status.HTTP_400_BAD_REQUEST)

        transfer.status = 'FRM'
        transfer.formed_at = timezone.now()
        transfer.save()
        return Response(status=status.HTTP_200_OK)

    def complete(self, request: Request, transfer_id: int):
        transfer: FileTransfer = get_object_or_404(self.model_class, id=transfer_id)
        if transfer.status != 'FRM':
            return Response({'error': 'Передача файлов еще не сформирована!'}, status=status.HTTP_400_BAD_REQUEST)

        empty_fields = []
        if not transfer.recipients.count():
            empty_fields.append('recipients field is empty')

        if not transfer.file:
            empty_fields.append('no files selected for transfer')

        if empty_fields:
            return Response({'error': empty_fields}, status=status.HTTP_400_BAD_REQUEST)

        if request.data['action'] == 'complete':
            transfer.status = 'COM'
        elif request.data['action'] == 'rejected':
            transfer.status = 'REJ'
        else:
            return Response({'error': 'No action specified'}, status=status.HTTP_400_BAD_REQUEST)

        transfer.completed_at = timezone.now()
        transfer.moderator = UserSingleton.get_instance()
        transfer.save()
        return Response(status=status.HTTP_200_OK)

    def delete(self, request, transfer_id):
        transfer = get_object_or_404(self.model_class, id=transfer_id)
        transfer.status = 'DEL'
        transfer.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class FileTransferRecipientDetails(APIView):
    model = FileTransferRecipient
    serializer_class = FileTransferRecipientSerializer

    def delete(self, id):
        # TODO: БЕЗ PK?
        transfer_recipient = get_object_or_404(FileTransferRecipient, id=id)
        transfer_recipient.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def put(self, id):
        transfer_recipient = get_object_or_404(FileTransferRecipient, id=id)
        transfer_recipient.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
