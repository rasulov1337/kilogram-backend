from datetime import datetime
from drf_yasg.utils import swagger_auto_schema

from django.contrib.auth import authenticate
from django.core.exceptions import ObjectDoesNotExist
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.timezone import make_aware
from minio import Minio
from rest_framework import status
from rest_framework.decorators import (
    api_view,
    permission_classes,
    authentication_classes,
)
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import viewsets

from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponse
from rest_framework.permissions import AllowAny
from django.views.decorators.csrf import csrf_exempt

from app.models import Recipient, FileTransfer, FileTransferRecipient, CustomUser
from app.serializers import (
    RecipientSerializer,
    FileTransferSerializer,
    FileTransferRecipientSerializer,
    UserSerializer,
)

from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponse
from rest_framework.permissions import AllowAny
from django.views.decorators.csrf import csrf_exempt
from rip import settings
from app.permissions import IsAdmin, IsModerator
import uuid

import redis

# Connect to our Redis instance
session_storage = redis.StrictRedis(host=settings.REDIS_HOST, port=settings.REDIS_PORT)


class MinioClient:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = Minio(
                endpoint=settings.AWS_S3_ENDPOINT_URL,
                access_key=settings.AWS_ACCESS_KEY_ID,
                secret_key=settings.AWS_SECRET_ACCESS_KEY,
                secure=settings.MINIO_USE_SSL,
            )
        return cls._instance


def method_permission_classes(classes):
    def decorator(func):
        def decorated_func(self, *args, **kwargs):
            self.permission_classes = classes
            self.check_permissions(self.request)
            return func(self, *args, **kwargs)

        return decorated_func

    return decorator


def load_file(file: InMemoryUploadedFile):
    client = MinioClient()

    img_obj_name = str(uuid.uuid4()) + "." + file.name.split(".")[-1]

    if not file:
        raise Exception("Не указан путь к файлу")

    client.put_object(
        bucket_name=settings.AWS_STORAGE_BUCKET_NAME,
        object_name=img_obj_name,
        data=file,
        length=file.size,
    )
    url_to_img = "http://localhost:9000/%s/%s" % (
        settings.AWS_STORAGE_BUCKET_NAME,
        img_obj_name,
    )

    return url_to_img


def delete_file(file_name: str):
    client = MinioClient()
    client.remove_object(settings.AWS_STORAGE_BUCKET_NAME, file_name)


class RecipientList(APIView):
    model_class = Recipient
    serializer_class = RecipientSerializer
    permission_classes = [AllowAny]

    # Get list of all recipients
    def get(self, request):
        user = request.user

        if "recipient-name" in request.GET:
            recipient_name = request.GET["recipient-name"]
            recipients = self.model_class.objects.filter(
                name__istartswith=recipient_name, status="A"
            )
        else:
            recipients = self.model_class.objects.filter(status="A")

        serializer = self.serializer_class(recipients, many=True)
        data = serializer.data

        draft = FileTransfer.objects.get_draft(user.id)
        if draft:
            data.append(
                {"draftId": draft.id, "draftRecipientsLen": len(draft.recipients.all())}
            )
        return Response(data)

    @method_permission_classes([IsModerator])
    @swagger_auto_schema(request_body=serializer_class)
    def post(self, request):
        data = request.data
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

    @method_permission_classes([IsModerator])
    @swagger_auto_schema(request_body=serializer_class)
    def put(self, request, recipient_id):
        recipient = get_object_or_404(self.model_class, id=recipient_id)
        serializer = self.serializer_class(recipient, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @method_permission_classes([IsModerator])
    def delete(self, request, recipient_id):
        recipient = get_object_or_404(self.model_class, id=recipient_id)
        if recipient.status == "D":
            return Response(
                {"error": "Recipient already deleted"}, status.HTTP_400_BAD_REQUEST
            )
        try:
            delete_file(recipient.avatar.split("/")[-1])
        except Exception as e:
            return Response({"error": str(e)}, status.HTTP_500_INTERNAL_SERVER_ERROR)
        recipient.status = "D"
        recipient.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class RecipientDetailDraft(APIView):
    model_class = Recipient
    serializer_class = RecipientSerializer

    """ Adds recipient to the draft """

    def post(self, request, recipient_id):
        if not request.user.is_authenticated:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        recipient = get_object_or_404(Recipient, id=recipient_id)
        draft_transfer = FileTransfer.objects.get_draft(request.user.id)
        if not draft_transfer:
            draft_transfer = FileTransfer.objects.create(
                status="DRF", sender=request.user
            )
            draft_transfer.save()

        if draft_transfer.recipients.contains(recipient):
            return Response(
                data={"error": "User already added"}, status=status.HTTP_400_BAD_REQUEST
            )

        draft_transfer.recipients.add(recipient, through_defaults={})
        draft_transfer.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class RecipientDetailAvatar(APIView):
    model_class = Recipient
    serializer_class = RecipientSerializer

    """ Adds avatar to the recipient """

    def post(self, request, recipient_id):
        avatar = request.FILES.get("avatar", None)

        if not avatar:
            return Response(
                {"error": "Файл с изображением не загружен"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        recipient = get_object_or_404(Recipient, id=recipient_id)

        try:
            if recipient.avatar:
                delete_file(recipient.avatar.split("/")[-1])

            avatar_url = load_file(avatar)
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        recipient.avatar = avatar_url
        recipient.save()

        return Response(
            {"message": "Изображение обновлено", "avatar": avatar_url},
            status=status.HTTP_200_OK,
        )


class FileTransferList(APIView):
    model_class = FileTransfer
    serializer_class = FileTransferSerializer

    def get(self, request):
        user = request.user
        status_filter = formed_at_range = None

        if "status" in request.GET:
            status_filter = request.GET["status"]
        if "formed-at-range" in request.GET:
            formed_at_range = list(
                map(
                    lambda x: datetime.strptime(x, "%Y-%m-%d"),
                    request.GET["formed-at-range"].split(","),
                )
            )
            formed_at_range[0] = make_aware(formed_at_range[0])
            formed_at_range[1] = make_aware(formed_at_range[1])
        transfers = self.model_class.objects.filter(
            ~(Q(status="DRF") | Q(status="DEL")), sender=user
        )
        if status_filter:
            transfers = transfers.filter(status=status_filter)
        if formed_at_range:
            transfers = transfers.filter(formed_at__range=formed_at_range)
        serializer = self.serializer_class(transfers, many=True)
        return Response(serializer.data)


class FileTransferDetails(APIView):
    model_class = FileTransfer
    serializer_class = FileTransferSerializer

    def get(self, request: Request, transfer_id):
        if not request.path.split("/")[-1].isdecimal():
            return Response(
                {"error": "method not allowed"}, status.HTTP_405_METHOD_NOT_ALLOWED
            )

        transfer = get_object_or_404(self.model_class, id=transfer_id)
        serializer = self.serializer_class(transfer)

        data = serializer.data
        data["recipients"] = self.model_class.objects.get_recipients_info(transfer_id)
        return Response(data)

    @method_permission_classes([IsModerator])
    @swagger_auto_schema(request_body=serializer_class)
    def put(self, request: Request, transfer_id):
        if request.path.endswith("/form"):
            return self.form(request, transfer_id)
        elif request.path.endswith("/complete"):
            return self.complete(request, transfer_id)
        elif request.path.split("/")[-1].isdecimal():
            return self.edit(request, transfer_id)
        raise Http404

    def edit(self, request: Request, transfer_id: int):
        # First check all new info except for the file
        transfer: FileTransfer = get_object_or_404(self.model_class, id=transfer_id)
        serializer = self.serializer_class(transfer, data=request.data, partial=True)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        if transfer.file:
            delete_file(transfer.file.split("/")[-1])

        serializer.save()

        # Then upload the file
        file_url = load_file(request.FILES["file_obj"])
        transfer.file = file_url
        transfer.save()

        return Response(serializer.data)

    def form(self, request: Request, transfer_id: int):
        transfer: FileTransfer = get_object_or_404(self.model_class, id=transfer_id)
        if transfer.status == "FRM":
            return Response(
                {"error": "The transfer is already formed"}, status.HTTP_400_BAD_REQUEST
            )

        empty_fields = []
        if not transfer.recipients.count():
            empty_fields.append("recipients field is empty")

        if not transfer.file:
            empty_fields.append("no files selected for transfer")

        if empty_fields:
            return Response({"error": empty_fields}, status=status.HTTP_400_BAD_REQUEST)

        transfer.status = "FRM"
        transfer.formed_at = timezone.now()
        transfer.save()
        return Response(status=status.HTTP_200_OK)

    @method_permission_classes([IsModerator])
    def complete(self, request: Request, transfer_id: int):
        transfer: FileTransfer = get_object_or_404(self.model_class, id=transfer_id)
        if transfer.status == "REJ" or transfer.status == "COM":
            return Response(
                {"error": "Передача файлов уже сформирована/отклонена!"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if transfer.status != "FRM":
            return Response(
                {"error": "Передача файлов еще не сформирована!"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        empty_fields = []
        if not transfer.recipients.count():
            empty_fields.append("recipients field is empty")

        if not transfer.file:
            empty_fields.append("no files selected for transfer")

        if empty_fields:
            return Response({"error": empty_fields}, status=status.HTTP_400_BAD_REQUEST)

        action = request.data.get("action", None)
        if action == "complete":
            transfer.status = "COM"
        elif action == "reject":
            transfer.status = "REJ"
        else:
            return Response(
                {"error": "No action specified"}, status=status.HTTP_400_BAD_REQUEST
            )

        transfer.completed_at = timezone.now()
        transfer.moderator = request.user
        FileTransferRecipient.objects.filter(file_transfer=transfer).update(
            sent_at=timezone.now()
        )
        transfer.save()
        return Response(status=status.HTTP_200_OK)

    def delete(self, request, transfer_id):
        if not request.path.split("/")[-1].isdecimal():
            return Response(
                {"error": "method not allowed"}, status.HTTP_405_METHOD_NOT_ALLOWED
            )
        transfer = get_object_or_404(self.model_class, id=transfer_id)
        if transfer.status != "DRF":
            return Response({"error": "Can not delete transfer that is not draft"})
        if transfer.status == "DEL":
            return Response(
                {"error": "Transfer already deleted"}, status.HTTP_400_BAD_REQUEST
            )
        transfer.status = "DEL"
        transfer.completed_at = timezone.now()
        FileTransferRecipient.objects.filter(file_transfer__id=transfer.id).delete()
        transfer.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class FileTransferRecipientDetails(APIView):
    model_class = FileTransferRecipient
    serializer_class = FileTransferRecipientSerializer

    def delete(self, request: Request, transfer_id: int, recipient_id: int):
        transfer = get_object_or_404(FileTransfer, id=transfer_id)
        transfer_recipient = get_object_or_404(
            self.model_class, file_transfer=transfer, recipient__id=recipient_id
        )

        transfer_recipient.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @swagger_auto_schema(request_body=serializer_class)
    def put(self, request: Request, transfer_id: int, recipient_id: int):
        transfer = get_object_or_404(FileTransfer, id=transfer_id)
        transfer_recipient = get_object_or_404(
            self.model_class, file_transfer=transfer, recipient__id=recipient_id
        )

        serializer = self.serializer_class(
            transfer_recipient, data=request.data, partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status.HTTP_400_BAD_REQUEST)


# class UserView(APIView):
#     model_class = CustomUser
#     serializer_class = UserSerializer

#     @swagger_auto_schema(request_body=serializer_class)
#     def post(self, request: Request, action: str):
#         if action == "signin":
#             return self.signin(request)
#         elif action == "signup":
#             return self.signup(request)
#         elif action == "signout":
#             return self.signout(request)
#         return Response({"error": "Wrong action"}, status=400)

#     @swagger_auto_schema(request_body=serializer_class)
#     def put(self, request: Request, action: str):
#         if action == "edit":
#             return self.edit(request)
#         return Response({"error": "Wrong action"}, status=400)

#     def signup(self, request: Request):
#         serializer = UserSerializer(data=request.data)
#         if serializer.is_valid():
#             serializer.save()
#             return Response(
#                 {"message": "Successful registration"}, status=status.HTTP_201_CREATED
#             )
#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

#     def edit(self, request: Request):
#         user = request.user
#         if user is None:
#             return Response(
#                 {"error": "Unauthorized"}, status=status.HTTP_401_UNAUTHORIZED
#             )

#         serializer = UserSerializer(user, data=request.data, partial=True)
#         if serializer.is_valid():
#             serializer.save()
#             return Response(
#                 {"message": "User updated", "user": serializer.data},
#                 status=status.HTTP_200_OK,
#             )
#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserViewSet(viewsets.ModelViewSet):
    """Класс, описывающий методы работы с пользователями
    Осуществляет связь с таблицей пользователей в базе данных
    """

    queryset = CustomUser.objects.all()
    serializer_class = UserSerializer
    model_class = CustomUser

    def create(self, request):
        """
        Функция регистрации новых пользователей
        Если пользователя c указанным в request username ещё нет, в БД будет добавлен новый пользователь.
        """
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            if self.model_class.objects.filter(
                username=request.data["username"]
            ).exists():
                return Response({"status": "Exist"}, status=400)

            self.model_class.objects.create_user(
                username=serializer.data["username"],
                password=serializer.data["password"],
                is_superuser=serializer.data["is_superuser"],
                is_staff=serializer.data["is_staff"],
            )
            return Response({"status": "Success"}, status=200)
        return Response(
            {"status": "Error", "error": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def get_permissions(self):
        if self.action in ["create"]:
            permission_classes = [AllowAny]
        elif self.action in ["list"]:
            permission_classes = [IsAdmin | IsManager]
        else:
            permission_classes = [IsAdmin]
        return [permission() for permission in permission_classes]


def method_permission_classes(classes):
    def decorator(func):
        def decorated_func(self, *args, **kwargs):
            self.permission_classes = classes
            self.check_permissions(self.request)
            return func(self, *args, **kwargs)

        return decorated_func

    return decorator


@permission_classes(
    [
        AllowAny,
    ]
)
@authentication_classes([])
def signin(request):
    username = request.data["username"]
    password = request.data["password"]
    user = authenticate(request, username=username, password=password)
    if user is not None:
        random_key = str(uuid.uuid4())
        session_storage.set(random_key, username)

        response = HttpResponse("{'status': 'ok'}")
        response.set_cookie("session_id", random_key)

        return response
    else:
        return HttpResponse("{'status': 'error', 'error': 'login failed'}")


@permission_classes([AllowAny])
@authentication_classes([])
def signout(request):
    logout(request._request)
    return Response({"status": "Success"})
