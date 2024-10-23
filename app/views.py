from datetime import datetime

from django.contrib.auth import authenticate
from django.contrib.auth.models import User
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
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from app.models import Recipient, FileTransfer, FileTransferRecipient
from app.serializers import (
    RecipientSerializer,
    FileTransferSerializer,
    FileTransferRecipientSerializer,
    UserSerializer,
)
from rip import settings
import uuid


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
            cls._instance = Minio(
                endpoint=settings.AWS_S3_ENDPOINT_URL,
                access_key=settings.AWS_ACCESS_KEY_ID,
                secret_key=settings.AWS_SECRET_ACCESS_KEY,
                secure=settings.MINIO_USE_SSL,
            )
        return cls._instance


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

    # Get list of all recipients
    def get(self, request):
        user = UserSingleton.get_instance()

        if "recipient-name" in request.GET:
            recipient_name = request.GET["recipient-name"]
            recipients = self.model_class.objects.filter(
                name__istartswith=recipient_name, status="A"
            )
        else:
            recipients = self.model_class.objects.filter(status="A")

        serializer = self.serializer_class(recipients, many=True)
        data = serializer.data

        draftInfo = {"draftId": None, "draftRecipientsLen": 0}

        draft = FileTransfer.objects.get_draft(user.id)
        if draft:
            draftInfo["draftId"] = draft.id
            draftInfo["draftRecipientsLen"] = len(draft.recipients.all())
        data.append(draftInfo)
        return Response(data)

    # Create a new recipient
    def post(self, request):
        data = request.data
        data["user"] = UserSingleton.get_instance().id
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

    def post(self, request: Request, recipient_id):
        if request.path.endswith("/image/"):
            return self.image(request, recipient_id)
        elif request.path.endswith("/draft/"):
            return self.draft(request, recipient_id)
        raise Http404

    def draft(self, request, recipient_id):
        if not UserSingleton.get_instance().is_authenticated:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        recipient = get_object_or_404(Recipient, id=recipient_id)
        draft_transfer = FileTransfer.objects.get_draft(UserSingleton.get_instance().id)
        if not draft_transfer:
            draft_transfer = FileTransfer.objects.create(
                status="DRF", sender=UserSingleton.get_instance()
            )
            draft_transfer.save()

        if draft_transfer.recipients.contains(recipient):
            return Response(
                data={"error": "User already added"}, status=status.HTTP_400_BAD_REQUEST
            )

        draft_transfer.recipients.add(recipient, through_defaults={})
        draft_transfer.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def image(self, request, recipient_id):
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
        # user = request.user
        user = UserSingleton.get_instance()
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

    def complete(self, request: Request, transfer_id: int):
        # TODO: проверка статуса модера
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
        transfer.moderator = UserSingleton.get_instance()
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


class UserView(APIView):
    def post(self, request: Request, action: str):
        if action == "signin":
            return self.signin(request)
        elif action == "signup":
            return self.signup(request)
        elif action == "signout":
            return self.signout(request)
        return Response({"error": "Wrong action"}, status=400)

    def put(self, request: Request, action: str):
        if action == "edit":
            return self.edit(request)
        return Response({"error": "Wrong action"}, status=400)

    def signup(self, request: Request):
        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"message": "Successful registration"}, status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def signin(self, request: Request):
        pass

    def signout(self, request: Request):
        pass

    def edit(self, request: Request):
        user = UserSingleton.get_instance()
        if user is None:
            return Response(
                {"error": "Unauthorized"}, status=status.HTTP_401_UNAUTHORIZED
            )

        serializer = UserSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"message": "User updated", "user": serializer.data},
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
