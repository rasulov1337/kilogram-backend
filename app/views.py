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

    process = FileSendingProcess.objects.filter(status='DRF', sender=request.user.id).first()

    draft = FileSendingProcess.objects.get_draft(request.user.id)

    return render(request, 'index.html', {
        'process': process,
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


def del_from_process(request, recipient_id: int):
    process = FileSendingProcess.objects.get_draft(request.user.id)
    if not process:
        process = FileSendingProcess.objects.create(status='DRF', sender=request.user)
    recipient = get_object_or_404(Recipient, id=recipient_id)
    process.recipients.remove(recipient)
    process.save()
    return redirect('draft-process')


def draft_process(request):
    process = FileSendingProcess.objects.get_draft(request.user.id)
    if not process:
        return redirect('index')

    recipients = list(process.recipients.all())
    return render(request, 'process.html', {
        'process': process,
        'recipients': recipients,
        'recipients_num': len(recipients)
    })


def del_draft(request):
    with connection.cursor() as cursor:
        cursor.execute("UPDATE app_filesendingprocess SET status='DEL' WHERE status!='DEL' and sender_id=%s",
                       [request.user.id])

    return redirect('index')


def process(request, process_id):
    pass


def profile(request, profile_id):
    needed_profile = Recipient.objects.get(id=profile_id)
    return render(request, 'profile.html', {
        'profile': needed_profile
    })
