from django.shortcuts import render
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_protect

AVATARS_BASE_URL = 'http://127.0.0.1:9000/launchbox/'
RECIPIENTS = [
    {
        'name': 'Johnathan Joestar',
        'id': 1,
        'city': 'Москва',
        'phone': '+7 777 777 7777',
        'uni': 'МГТУ им. Баумана',
        'birthdate': '1 января 2000 г',
        'status': 'Хочу больше лета...',
        'avatar': AVATARS_BASE_URL + '1.jpg',
    },
    {
        'name': 'John Doe',
        'id': 2,
        'city': 'Абу-Даби',
        'phone': '+1 777 777 7777',
        'uni': 'МГТУ им. Баумана',
        'birthdate': '1 мая 2004 г',
        'status': 'Отвечаю вечером',
        'avatar': AVATARS_BASE_URL + '2.avif',
    },
    {
        'name': 'Anna Smith',
        'id': 3,
        'city': 'Лондон',
        'phone': '+44 123 456 7890',
        'uni': 'Imperial College London',
        'birthdate': '15 февраля 1999 г',
        'status': 'Занята работой',
        'avatar': AVATARS_BASE_URL + '3.jpg'
    },
    {
        'name': 'Алексей Иванов',
        'id': 4,
        'city': 'Санкт-Петербург',
        'phone': '+7 999 888 7777',
        'uni': 'СПбГУ',
        'birthdate': '30 сентября 2001 г',
        'status': 'Жду выходных',
        'avatar': AVATARS_BASE_URL + '4.avif'
    },
    {
        'name': 'Maria Gonzalez',
        'id': 5,
        'city': 'Мадрид',
        'phone': '+34 654 321 987',
        'uni': 'Universidad Complutense de Madrid',
        'birthdate': '8 марта 1998 г',
        'status': 'На конференции',
        'avatar': AVATARS_BASE_URL + '5.jpg',
    },
    {
        'name': 'Chen Wei',
        'id': 6,
        'city': 'Пекин',
        'phone': '+86 10 8888 9999',
        'uni': 'Peking University',
        'birthdate': '22 июня 2002 г',
        'status': 'Студент',
        'avatar': AVATARS_BASE_URL + '6.jpg',
    },
    {
        'name': 'Oliver Brown',
        'id': 7,
        'city': 'Нью-Йорк',
        'phone': '+1 212 555 1234',
        'uni': 'New York University',
        'birthdate': '5 ноября 2000 г',
        'status': 'Работаю над проектом',
        'avatar': AVATARS_BASE_URL + '7.jpg',

    }
]

SEND_QUEUES = {
    1: {
        'id': 1,
        'files': [],
        'recipients': RECIPIENTS[:3],
        'recipients_num': 3
    }
}


@csrf_protect
def index(request):
    recipients = []

    if request.method == 'POST':
        search_query = request.POST['search_query'].lower()
        for i in RECIPIENTS:
            if i['name'].lower().startswith(search_query):
                recipients.append(i)
    else:
        recipients.extend(RECIPIENTS)

    return render(request, 'index.html', {
        'order': SEND_QUEUES[1],
        'recipients': recipients,
        'recipients_count': len(recipients)
    })


def order(request, order_id):
    if order_id not in SEND_QUEUES:
        return HttpResponse('Wrong order_id')
    return render(request, 'order.html', {
        'order': SEND_QUEUES[order_id]
    })


def profile(request, profile_id):
    needed_profile = None
    for i in RECIPIENTS:
        if i['id'] == int(profile_id):
            needed_profile = i
    return render(request, 'profile.html', {
        'profile': needed_profile
    })
