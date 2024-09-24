import django.db.models
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


class FileSendingProcessManager(models.Manager):
    def get_draft(self, user_id: int):
        try:
            return self.get(status='DRF', sender=user_id)
        except self.model.DoesNotExist:
            return None


class File(models.Model):
    url = models.URLField()
    format = models.CharField(max_length=8)
    size = models.IntegerField()  # In Bytes

    def __str__(self):
        return self.url


class FileSendingProcess(models.Model):
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
    recipients = models.ManyToManyField(Recipient, through="FileSendingProcessRecipient")
    files = models.ManyToManyField(File)

    objects = FileSendingProcessManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['sender'], condition=models.Q(status='draft'),
                                    name='unique_draft_per_sender')
        ]

    def __str__(self):
        return self.status + ' ' + self.sender.recipient.name + ' ' + self.created_at.strftime('%Y-%m-%d %H:%M')


class FileSendingProcessRecipient(models.Model):
    file_sending_process = models.ForeignKey(FileSendingProcess, on_delete=models.CASCADE)
    recipient = models.ForeignKey(Recipient, on_delete=models.CASCADE)
    comment = models.CharField(max_length=200, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['file_sending_process', 'recipient', 'comment'],
                                    name='unique_proc_recipient_comment')
        ]
