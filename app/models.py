from django.db import models
from django.contrib.auth.models import (
    AbstractBaseUser,
    UserManager,
    PermissionsMixin,
)


class NewUserManager(UserManager):
    def create_user(self, username, password=None, **extra_fields):
        if not username:
            raise ValueError("User must have an username")

        user = self.model(username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self.db)

        return user

    def create_superuser(self, username, password=None, **extra_fields):
        user = self.model(username=username, **extra_fields)
        user.set_password(password)
        user.is_superuser = True
        user.save(using=self.db)

        return user


class CustomUser(AbstractBaseUser, PermissionsMixin):
    username = models.CharField(verbose_name=("Username"), unique=True, max_length=50)
    password = models.CharField(verbose_name="Password")
    is_staff = models.BooleanField(
        default=False, verbose_name="Является ли пользователь менеджером?"
    )
    is_superuser = models.BooleanField(
        default=False, verbose_name="Является ли пользователь админом?"
    )

    USERNAME_FIELD = "username"

    objects = NewUserManager()


class Recipient(models.Model):
    STATUS_CHOICES = [("A", "Active"), ("D", "Deleted")]
    name = models.CharField(max_length=90)
    desc = models.CharField(max_length=140)
    phone = models.CharField(max_length=18, unique=True)
    city = models.CharField(max_length=40)
    birthdate = models.DateField()
    status = models.CharField(max_length=1, choices=STATUS_CHOICES, default="A")
    avatar = models.URLField(blank=True, null=True)
    uni = models.CharField(max_length=140)

    def __str__(self):
        return self.name


class FileTransferManager(models.Manager):
    def get_draft(self, user_id: int):
        try:
            return self.get(status="DRF", sender=user_id)
        except self.model.DoesNotExist:
            return None

    def get_recipients_info(self, transfer_id: int):
        res = []
        for transfer_recipient in FileTransferRecipient.objects.filter(
            file_transfer_id=transfer_id
        ):
            res.append(
                {
                    "id": transfer_recipient.recipient.id,
                    "name": transfer_recipient.recipient.name,
                    "phone": transfer_recipient.recipient.phone,
                    "avatar": transfer_recipient.recipient.avatar,
                    "comment": transfer_recipient.comment,
                }
            )
        return res


class FileTransfer(models.Model):
    STATUS_CHOICES = [
        ("DRF", "Draft"),
        ("DEL", "Deleted"),
        ("FRM", "Formed"),
        ("COM", "Completed"),
        ("REJ", "Rejected"),
    ]
    status = models.CharField(max_length=3, choices=STATUS_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    formed_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    sender = models.ForeignKey(
        CustomUser, on_delete=models.PROTECT, related_name="sender"
    )
    moderator = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, related_name="moderator"
    )
    recipients = models.ManyToManyField(Recipient, through="FileTransferRecipient")
    file = models.URLField(blank=True, null=True)

    objects = FileTransferManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["sender"],
                condition=models.Q(status="draft"),
                name="unique_draft_per_sender",
            )
        ]

    def __str__(self):
        return (
            self.status
            + " "
            + self.sender.get_full_name()
            + " "
            + self.created_at.strftime("%Y-%m-%d %H:%M")
        )


class FileTransferRecipient(models.Model):
    file_transfer = models.ForeignKey(
        FileTransfer, on_delete=models.PROTECT, related_name="file_transfers"
    )
    recipient = models.ForeignKey(
        Recipient, on_delete=models.PROTECT, related_name="recipients"
    )
    comment = models.CharField(max_length=200, blank=True, null=True)
    has_read = models.BooleanField(default=False)  # Is calculated on send

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["file_transfer", "recipient"], name="unique_transfer_recipient"
            )
        ]
