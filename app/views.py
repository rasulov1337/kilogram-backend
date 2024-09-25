from django.shortcuts import render, get_object_or_404, redirect
from django.db import connection

from app.models import Recipient, FileTransfer


def index(request):
    recipients = []
    recipient_name = ''

    if 'recipient-name' in request.GET:
        recipient_name = request.GET['recipient-name']
        recipients.extend(Recipient.objects.filter(name__istartswith=recipient_name))
    else:
        recipients.extend(Recipient.objects.all())

    draft = FileTransfer.objects.get_draft(request.user.id)

    return render(request, 'index.html', {
        'transfer': draft,
        'recipients': recipients,
        'recipients_num': len(draft.recipients.all()) if draft else None,
        'old_recipient_name': recipient_name
    })


def add_to_transfer(request, recipient_id: int):
    transfer = FileTransfer.objects.get_draft(request.user.id)
    if not transfer:
        transfer = FileTransfer.objects.create(status='DRF', sender=request.user)
    recipient = get_object_or_404(Recipient, id=recipient_id)
    transfer.recipients.add(recipient, through_defaults={})
    transfer.save()
    return redirect('index')


def transfer(request, process_id: int):
    transfer = get_object_or_404(FileTransfer, id=process_id)
    if not transfer:
        return redirect('index')

    recipients = list(transfer.recipients.all())
    return render(request, 'transfer.html', {
        'transfer': transfer,
        'recipients': recipients,
        'recipients_num': len(recipients)
    })


def del_transfer(request, process_id: int):
    with connection.cursor() as cursor:
        cursor.execute("UPDATE app_filetransfer SET status='DEL' WHERE id=%s",
                       [process_id])

    return redirect('index')


def profile(request, profile_id):
    needed_profile = Recipient.objects.get(id=profile_id)
    return render(request, 'profile.html', {
        'profile': needed_profile
    })
