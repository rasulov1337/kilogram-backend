import uuid
from datetime import datetime
import random

import redis
from django.contrib.auth import authenticate
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.db.models import Q, Count
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.timezone import make_aware
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from minio import Minio
from rest_framework import status, viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
    action,
)
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from app.models import CustomUser, FileTransfer, FileTransferRecipient, Recipient
from app.permissions import IsAdmin, IsAnon, IsModerator
from app.serializers import (
    FileTransferRecipientSerializer,
    FileTransferSerializer,
    RecipientSerializer,
    UserSerializer,
)
from rip import settings


class CsrfExemptSessionAuthentication(SessionAuthentication):
    def enforce_csrf(self, request):
        pass


# Connect to our Redis instance
session_storage = redis.StrictRedis(host=settings.REDIS_HOST, port=settings.REDIS_PORT)

minio_client = Minio(
    endpoint=settings.AWS_S3_ENDPOINT_URL,
    access_key=settings.AWS_ACCESS_KEY_ID,
    secret_key=settings.AWS_SECRET_ACCESS_KEY,
    secure=settings.MINIO_USE_SSL,
)


def method_permission_classes(classes):
    def decorator(func):
        def decorated_func(self, *args, **kwargs):
            self.permission_classes = classes
            self.check_permissions(self.request)
            return func(self, *args, **kwargs)

        return decorated_func

    return decorator


def load_file(file: InMemoryUploadedFile):
    client = minio_client

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
    client = minio_client
    client.remove_object(settings.AWS_STORAGE_BUCKET_NAME, file_name)


class RecipientList(APIView):
    model_class = Recipient
    serializer_class = RecipientSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    # Get list of all recipients
    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                "recipient-name",
                openapi.IN_QUERY,
                description="Used for filtration by recipient's name",
                type=openapi.TYPE_STRING,
            )
        ]
    )
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

        draftInfo = {"draftId": None, "draftRecipientsCount": 0}

        draft = FileTransfer.objects.get_draft(user.id)

        if draft:
            draftInfo["draftId"] = draft.id
            draftInfo["draftRecipientsCount"] = (
                Recipient.objects.filter(filetransfer=draft)
                .aggregate(draft_recipients_count=Count("*"))
                .get("draft_recipients_count")
            )

        data.append(draftInfo)
        return Response(data)

    @swagger_auto_schema(request_body=RecipientSerializer)
    @method_permission_classes([IsModerator])
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RecipientDetail(APIView):
    model_class = Recipient
    serializer_class = RecipientSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request, recipient_id):
        recipient = get_object_or_404(self.model_class, id=recipient_id)
        serializer = self.serializer_class(recipient)
        return Response(serializer.data)

    @swagger_auto_schema(request_body=serializer_class)
    @method_permission_classes([IsModerator])
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
    permission_classes = [IsAuthenticated]

    """ Adds recipient to the draft """

    @swagger_auto_schema(
        operation_description="Adds recipient to the user's draft file transfer"
    )
    def post(self, request, recipient_id):
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
    permission_classes = [IsModerator]

    """ Adds avatar to the recipient """

    @swagger_auto_schema(
        operation_description="Adds avatar to the recipient",
        request_body=openapi.Schema(
            type=openapi.TYPE_FILE,
            format=openapi.FORMAT_BINARY,
            description="New avatar",
        ),
    )
    def post(self, request, recipient_id):
        avatar = request.FILES.get("avatar", None)

        if not avatar:
            return Response(
                {"error": "File was not uploaded"},
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
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                "status",
                openapi.IN_QUERY,
                description="Filter by status",
                type=openapi.TYPE_STRING,
            ),
            openapi.Parameter(
                "formed-at-range",
                openapi.IN_QUERY,
                description="Filter by range which the transfer was formed at (Type as: %Y-%m-%d,%Y-%m-%d)",
                type=openapi.TYPE_STRING,
            ),
        ]
    )
    def get(self, request):
        if request.user.is_staff or request.user.is_superuser:
            return self.get_all_transfers(request)
        return self.get_transfers_of_user(request)

    def get_transfers_of_user(self, request: Request):
        transfers = self.model_class.objects.filter(
            ~(Q(status="DRF") | Q(status="DEL")), sender=request.user
        )

        transfers = self._filter_transfers(request, transfers)
        serializer = self.serializer_class(transfers, many=True)
        return Response(serializer.data)

    @method_permission_classes([IsModerator])
    def get_all_transfers(self, request: Request):
        transfers = self.model_class.objects.all()
        transfers = self._filter_transfers(request, transfers)

        serializer = self.serializer_class(transfers, many=True)
        return Response(serializer.data)

    def _filter_transfers(self, request: Request, transfers):
        status_filter = formed_at_range = None

        if "status" in request.GET:
            status_filter = request.GET["status"]
        try:
            if "formed-at-range" in request.GET:
                formed_at_range = list(
                    map(
                        lambda x: datetime.strptime(x, "%Y-%m-%d"),
                        request.GET["formed-at-range"].split(","),
                    )
                )
                formed_at_range[0] = make_aware(formed_at_range[0])
                formed_at_range[1] = make_aware(formed_at_range[1])
        except Exception:
            print("Wrong date format detected. Returning nothing")
            return []

        if status_filter:
            transfers = transfers.filter(status=status_filter)
        if formed_at_range:
            transfers = transfers.filter(formed_at__range=formed_at_range)
        return transfers


class FileTransferDetails(APIView):
    model_class = FileTransfer
    serializer_class = FileTransferSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, transfer_id: int):
        transfer = get_object_or_404(self.model_class, id=transfer_id)
        if (
            not request.user.is_staff
            and not request.user.is_superuser
            and request.user != transfer.sender
        ):
            return Response(
                {"error": "You do not have permission to view this transfer"},
                status.HTTP_403_FORBIDDEN,
            )

        serializer = self.serializer_class(transfer)

        data = serializer.data
        data["recipients"] = self.model_class.objects.get_recipients_info(transfer_id)
        return Response(data)

    @swagger_auto_schema(request_body=serializer_class)
    @method_permission_classes([IsAuthenticated])
    def put(self, request: Request, transfer_id):
        if not (
            request.user.is_staff
            or request.user.is_superuser
            or FileTransfer.objects.get(id=transfer_id).sender == request.user
        ):
            return Response(
                {"error": "You do not have permission to perform this action"},
                status.HTTP_403_FORBIDDEN,
            )

        # First check all new info except for the file
        transfer: FileTransfer = get_object_or_404(self.model_class, id=transfer_id)

        if (
            not request.user.is_staff
            and not request.user.is_superuser
            and transfer.sender != request.user
        ):
            return Response(
                {"error": "You do not have permissions to edit this transfer"},
                status.HTTP_403_FORBIDDEN,
            )

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

    def delete(self, request, transfer_id):
        transfer = get_object_or_404(self.model_class, id=transfer_id)

        if (
            not request.user.is_staff
            and not request.user.is_superuser
            and transfer.sender != request.user
        ):
            return Response(
                {"error": "You do not have permissions to delete this transfer"},
                status.HTTP_403_FORBIDDEN,
            )

        if transfer.status != "DRF":
            return Response(
                {"error": "Can not delete transfer that is not draft"},
                status.HTTP_400_BAD_REQUEST,
            )
        if transfer.status == "DEL":
            return Response(
                {"error": "Transfer already deleted"}, status.HTTP_400_BAD_REQUEST
            )
        transfer.status = "DEL"
        transfer.completed_at = timezone.now()
        FileTransferRecipient.objects.filter(file_transfer__id=transfer.id).delete()
        transfer.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class FileTransferDetailsForm(APIView):
    model_class = FileTransfer
    permission_classes = [IsAuthenticated]

    def put(self, request: Request, transfer_id: int):
        transfer: FileTransfer = get_object_or_404(self.model_class, id=transfer_id)
        if (
            not (request.user.is_staff or request.user.is_superuser)
            and transfer.sender != request.user
        ):
            return Response(
                {"error": "You do not have permissions to form this transfer"},
                status.HTTP_403_FORBIDDEN,
            )

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


class FileTransferDetailsComplete(APIView):
    model_class = FileTransfer
    permission_classes = [IsModerator]

    @swagger_auto_schema(
        operation_description="Completes the transfer",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "action": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Action: (reject|complete) the transfer",
                    default="complete",
                )
            },
            required=["action"],
        ),
    )
    def put(self, request: Request, transfer_id: int):
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
            has_read=bool(random.getrandbits(1))
        )
        transfer.save()
        return Response(status=status.HTTP_200_OK)


class FileTransferRecipientDetails(APIView):
    model_class = FileTransferRecipient
    serializer_class = FileTransferRecipientSerializer
    permission_classes = [IsAuthenticated]

    def delete(self, request: Request, transfer_id: int, recipient_id: int):
        transfer_recipient = get_object_or_404(
            self.model_class, file_transfer__id=transfer_id, recipient__id=recipient_id
        )
        transfer = get_object_or_404(FileTransfer, id=transfer_id)

        if (
            not (request.user.is_staff or request.user.is_superuser)
            and transfer.sender != request.user
        ):
            return Response(
                {"error": "You do not have permissions to form this transfer"},
                status.HTTP_403_FORBIDDEN,
            )

        transfer_recipient.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @swagger_auto_schema(request_body=serializer_class)
    def put(self, request: Request, transfer_id: int, recipient_id: int):
        transfer_recipient = get_object_or_404(
            self.model_class, file_transfer__id=transfer_id, recipient__id=recipient_id
        )

        serializer = self.serializer_class(
            transfer_recipient, data=request.data, partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status.HTTP_400_BAD_REQUEST)


class UserViewSet(viewsets.ModelViewSet):
    """Класс, описывающий методы работы с пользователями
    Осуществляет связь с таблицей пользователей в базе данных
    """

    queryset = CustomUser.objects.all()
    serializer_class = UserSerializer
    model_class = CustomUser

    @method_permission_classes([IsModerator, IsAuthenticated])
    def retrieve(self, request, pk=None):
        if str(request.user.id) != pk and not request.user.is_staff:
            return Response({"error": "Forbidden"}, status.HTTP_403_FORBIDDEN)

        return super().retrieve(request, pk)

    @method_permission_classes([IsAnon])
    def create(self, request):
        """
        Функция регистрации новых пользователей
        Если пользователя c указанным в request username ещё нет,
        в БД будет добавлен новый пользователь.
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
            )
            return Response({"status": "Success"}, status=200)
        return Response(
            {"status": "Error", "error": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    @action(detail=False, methods=["put"], permission_classes=[IsAuthenticated])
    def update_profile(self, request):
        user = self.model_class.objects.get(id=request.user.id)

        serializer = self.serializer_class(
            partial=True, instance=user, data=request.data
        )
        if serializer.is_valid():
            serializer.save()
            return Response({"status": "Success"}, status=200)
        return Response(
            {"status": "Error", "error": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def get_permissions(self):
        permission_classes = [IsAuthenticated]
        if self.action == "retrieve":
            permission_classes = [IsAuthenticated]
        elif self.action in ["update", "update_profile"]:
            permission_classes = [IsAuthenticated]
        elif self.action in ["list"]:
            permission_classes = [IsModerator]
        elif self.action in ["create"]:
            permission_classes = [IsAnon]
        else:
            permission_classes = [IsAdmin]
        return [permission() for permission in permission_classes]


@swagger_auto_schema(
    method="post",
    request_body=UserSerializer,
    operation_description="Signs the user in",
)
@api_view(["POST"])
@permission_classes([IsAnon])
@authentication_classes([CsrfExemptSessionAuthentication])
def signin(request):
    username = request.data.get("username", None)
    password = request.data.get("password", None)
    user = authenticate(request, username=username, password=password)
    if user is not None:
        random_key = str(uuid.uuid4())
        session_storage.set(random_key, user.id)

        response = Response({"status": "ok"})
        response.set_cookie("session_id", random_key)
        response.set_cookie("csrftoken", get_token(request))

        return response
    else:
        return Response(
            {"status": "error", "error": "login failed"},
            status=status.HTTP_401_UNAUTHORIZED,
        )


@permission_classes([IsAuthenticated])
@swagger_auto_schema(method="post", operation_description="Signs the user out")
@api_view(["POST"])
def signout(request):
    session_id = request.COOKIES.get("session_id")
    if session_id:
        session_storage.delete(session_id)
        response = Response({"status": "ok"})
        response.delete_cookie("session_id")
        return response
    else:
        return Response(
            {"status": "error", "error": "no session found"},
            status=status.HTTP_400_BAD_REQUEST,
        )


@permission_classes([IsAuthenticated])
@swagger_auto_schema(method="GET", operation_description="Gets session info")
@api_view(["GET"])
def session(request):
    user = request.user
    response = Response({"username": user.username, "user_id": user.id})
    return response
