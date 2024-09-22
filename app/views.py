from django.shortcuts import render
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_protect

RECIPIENTS = [
    {
        'name': 'Джонатан Джостер',
        'id': 1,
        'city': 'Москва',
        'phone': '+7 777 777 7777',
        'uni': 'МГТУ им. Баумана',
        'birthdate': '1 января 2000 г',
        'status': 'Хочу больше лета...',
        'avatar': 'http://127.0.0.1:9000/launchbox/1.jpg',
    },
    {
        'name': 'Джон Доу',
        'id': 2,
        'city': 'Абу-Даби',
        'phone': '+1 777 777 7777',
        'uni': 'МГТУ им. Баумана',
        'birthdate': '1 мая 2004 г',
        'status': 'Отвечаю вечером',
        'avatar': 'http://127.0.0.1:9000/launchbox/2.avif',
    },
    {
        'name': 'Анна Смит',
        'id': 3,
        'city': 'Лондон',
        'phone': '+44 123 456 7890',
        'uni': 'Imperial College London',
        'birthdate': '15 февраля 1999 г',
        'status': 'Занята работой',
        'avatar': 'http://127.0.0.1:9000/launchbox/3.jpg'
    },
    {
        'name': 'Алексей Иванов',
        'id': 4,
        'city': 'Санкт-Петербург',
        'phone': '+7 999 888 7777',
        'uni': 'СПбГУ',
        'birthdate': '30 сентября 2001 г',
        'status': 'Жду выходных',
        'avatar': 'http://127.0.0.1:9000/launchbox/4.avif'
    },
    {
        'name': 'Мариа Гонзалез',
        'id': 5,
        'city': 'Мадрид',
        'phone': '+34 654 321 987',
        'uni': 'Universidad Complutense de Madrid',
        'birthdate': '8 марта 1998 г',
        'status': 'На конференции',
        'avatar': 'http://127.0.0.1:9000/launchbox/5.jpg',
    },
    {
        'name': 'Оливер Браун',
        'id': 7,
        'city': 'Нью-Йорк',
        'phone': '+1 212 555 1234',
        'uni': 'New York University',
        'birthdate': '5 ноября 2000 г',
        'status': 'Работаю над проектом',
        'avatar': 'http://127.0.0.1:9000/launchbox/7.jpg',

    }
]

PROCESSES = {  # File sending processes
    1: {
        'id': 1,
        'files': [
            {
                'name': 'linal_rk1_reshenie_biletov.pdf',
                'size': '11.1 MB',
                'format': 'PDF'
            }
        ],
        'recipients': RECIPIENTS[:3],
        'recipients_num': 3
    }
}


def index(request):
    recipients = []
    recipient_name = ''

    if 'recipient-name' in request.GET:
        recipient_name = request.GET['recipient-name']
        for i in RECIPIENTS:
            if i['name'].lower().startswith(recipient_name.lower()):
                recipients.append(i)
    else:
        recipients.extend(RECIPIENTS)

    return render(request, 'index.html', {
        'process': PROCESSES[1],
        'recipients': recipients,
        'recipients_count': len(recipients),
        'old_recipient_name': recipient_name
    })


def sending_process(request, process_id):
    if process_id not in PROCESSES:
        return HttpResponse('Wrong order_id')
    return render(request, 'process.html', {
        'process': PROCESSES[process_id]
    })


def profile(request, profile_id):
    needed_profile = None
    for i in RECIPIENTS:
        if i['id'] == int(profile_id):
            needed_profile = i
    return render(request, 'profile.html', {
        'profile': needed_profile
    })
