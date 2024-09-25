from django.contrib import admin
from .models import Recipient, FileTransfer, File

admin.site.register(Recipient)
admin.site.register(FileTransfer)
admin.site.register(File)
