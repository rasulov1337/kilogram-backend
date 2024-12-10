from app.models import Recipient, FileTransfer, FileTransferRecipient
from rest_framework import serializers
from collections import OrderedDict
from app.models import CustomUser


class UserSerializer(serializers.ModelSerializer):
    # is_staff = serializers.BooleanField(default=False, required=False)
    # is_superuser = serializers.BooleanField(default=False, required=False)

    class Meta:
        model = CustomUser
        fields = [
            "username",
            "password",
        ]
        extra_kwargs = {
            "username": {"required": True},
            "password": {"write_only": True},
        }

    def update(self, instance, validated_data):
        if "password" in validated_data:
            password = validated_data.pop("password")
            instance.set_password(password)  # Use set_password for hashing

        return super().update(instance, validated_data)


class RecipientSerializer(serializers.ModelSerializer):
    class Meta:
        # Модель, которую мы сериализуем
        model = Recipient
        # Поля, которые мы сериализуем
        fields = ["id", "name", "desc", "phone", "city", "birthdate", "avatar", "uni"]

    def get_fields(self):
        new_fields = OrderedDict()
        for name, field in super().get_fields().items():
            field.required = False
            new_fields[name] = field
        return new_fields


class FileTransferSerializer(serializers.ModelSerializer):
    class Meta:
        model = FileTransfer
        fields = [
            "id",
            "status",
            "created_at",
            "formed_at",
            "completed_at",
            "sender",
            "moderator",
            "file",
        ]

    def to_representation(self, instance):
        repr = super().to_representation(instance)
        repr["sender"] = CustomUser.objects.get(id=repr["sender"]).username
        if repr["moderator"]:
            repr["moderator"] = CustomUser.objects.get(id=repr["moderator"]).username

        return repr

    def update(self, instance, validated_data):
        instance.file = validated_data.get("file", instance.file)
        instance.save()
        return instance

    def get_fields(self):
        new_fields = OrderedDict()
        for name, field in super().get_fields().items():
            field.required = False
            new_fields[name] = field
        return new_fields


class FileTransferRecipientSerializer(serializers.ModelSerializer):
    class Meta:
        model = FileTransferRecipient
        read_only_fields = ["file_transfer", "recipient", "has_read"]
        fields = "__all__"
