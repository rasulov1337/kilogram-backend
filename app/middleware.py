from django.http import HttpResponse
from app.views import session_storage
from app.models import CustomUser


def session_middleware(get_response):
    def middleware(request):
        # Code to be executed for each request before
        # the view (and later middleware) are called.

        ssid = request.COOKIES.get("session_id")
        if ssid and session_storage.exists(ssid):
            username = session_storage.get(ssid).decode("utf-8")
            request.user = CustomUser.objects.get(username=username)
        else:
            request.user = (
                None  # Устанавливаем пользователя в None, если сессия недействительна
            )

        response = get_response(request)

        # Code to be executed for each request/response after
        # the view is called.

        return response

    return middleware
