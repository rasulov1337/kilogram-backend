from django.contrib import admin
from .models import Recipient, FileSendingProcess, File

admin.site.register(Recipient)
admin.site.register(FileSendingProcess)
admin.site.register(File)
