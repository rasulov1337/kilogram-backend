from django.contrib.auth.models import User

from app.models import Recipient, FileTransfer, FileTransferRecipient
from rest_framework import serializers


class RecipientSerializer(serializers.ModelSerializer):
    class Meta:
        # Модель, которую мы сериализуем
        model = Recipient
        # Поля, которые мы сериализуем
        fields = ["id", "name", "desc", "phone", "city", "birthdate", "avatar", "uni"]


class UserSerializer(serializers.ModelSerializer):
    def create(self, validated_data):
        self.check_email(validated_data.get("email", None))
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"],
        )
        return user

    class Meta:
        model = User
        fields = ["id", "username", "email", "password"]
        extra_kwargs = {"password": {"write_only": True}, "email": {"required": True}}

    def validate_password(self, value):
        if not (8 <= len(value) <= 16):
            raise serializers.ValidationError(
                "Password's length should be between 8 and 16"
            )
        return value

    def check_email(self, value):
        if not value:
            raise serializers.ValidationError("Email is empty")

        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("User with that email already exists")


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
        repr["sender"] = User.objects.get(id=repr["sender"]).username
        if repr["moderator"]:
            repr["moderator"] = User.objects.get(id=repr["moderator"]).username

        return repr

    def update(self, instance, validated_data):
        instance.file = validated_data.get("file", instance.file)
        instance.save()
        return instance


class FileTransferRecipientSerializer(serializers.ModelSerializer):
    class Meta:
        model = FileTransferRecipient
        read_only_fields = ["file_transfer", "recipient", "sent_at"]
        fields = "__all__"
