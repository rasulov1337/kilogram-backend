from django.shortcuts import render, get_object_or_404, redirect
from django.db import connection

from app.models import Recipient, FileSendingProcess


def index(request):
    recipients = []
    recipient_name = ''

    if 'recipient-name' in request.GET:
        recipient_name = request.GET['recipient-name']
        recipients.extend(Recipient.objects.filter(name__istartswith=recipient_name))
    else:
        recipients.extend(Recipient.objects.all())

    draft = FileSendingProcess.objects.get_draft(request.user.id)

    return render(request, 'index.html', {
        'process': draft,
        'recipients': recipients,
        'recipients_num': len(draft.recipients.all()) if draft else None,
        'old_recipient_name': recipient_name
    })


def add_to_process(request, recipient_id: int):
    process = FileSendingProcess.objects.get_draft(request.user.id)
    if not process:
        process = FileSendingProcess.objects.create(status='DRF', sender=request.user)
    recipient = get_object_or_404(Recipient, id=recipient_id)
    process.recipients.add(recipient, through_defaults={})
    process.save()
    return redirect('index')


def process(request, process_id: int):
    process = get_object_or_404(FileSendingProcess, id=process_id)
    if not process:
        return redirect('index')

    recipients = list(process.recipients.all())
    return render(request, 'process.html', {
        'process': process,
        'recipients': recipients,
        'recipients_num': len(recipients)
    })


def del_process(request, process_id: int):
    with connection.cursor() as cursor:
        cursor.execute("UPDATE app_filesendingprocess SET status='DEL' WHERE id=%s",
                       [process_id])

    return redirect('index')


def profile(request, profile_id):
    needed_profile = Recipient.objects.get(id=profile_id)
    return render(request, 'profile.html', {
        'profile': needed_profile
    })
