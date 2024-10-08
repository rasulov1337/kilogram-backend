from django.contrib.auth.models import User
from django.db import models


class Recipient(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    STATUS_CHOICES = [
        ('A', 'Active'),
        ('D', 'Deleted')
    ]
    name = models.CharField(max_length=90)
    desc = models.CharField(max_length=140, blank=True)
    phone = models.CharField(max_length=18, unique=True)
    city = models.CharField(max_length=40)
    birthdate = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=1, choices=STATUS_CHOICES)
    avatar = models.URLField(blank=True, null=True)
    uni = models.CharField(max_length=140, blank=True, null=True)

    def __str__(self):
        return self.name


class FileTransferManager(models.Manager):
    def get_draft(self, user_id: int):
        try:
            return self.get(status='DRF', sender=user_id)
        except self.model.DoesNotExist:
            return None


class FileTransfer(models.Model):
    STATUS_CHOICES = [
        ('DRF', 'Draft'),
        ('DEL', 'Deleted'),
        ('FRM', 'Formed'),
        ('COM', 'Completed'),
        ('REJ', 'Rejected')
    ]
    status = models.CharField(max_length=3, choices=STATUS_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    formed_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='sender')
    moderator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='moderator')
    recipients = models.ManyToManyField(Recipient, through="FileTransferRecipient")
    file = models.URLField()

    objects = FileTransferManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['sender'], condition=models.Q(status='draft'),
                                    name='unique_draft_per_sender')
        ]

    def __str__(self):
        return self.status + ' ' + self.sender.recipient.name + ' ' + self.created_at.strftime('%Y-%m-%d %H:%M')


class FileTransferRecipient(models.Model):
    file_transfer = models.ForeignKey(FileTransfer, on_delete=models.CASCADE)
    recipient = models.ForeignKey(Recipient, on_delete=models.CASCADE)
    comment = models.CharField(max_length=200, blank=True)
    sent_at = models.DateTimeField(null=True)  # Is calculated on send

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['file_transfer', 'recipient'],
                                    name='unique_transfer_recipient')
        ]
