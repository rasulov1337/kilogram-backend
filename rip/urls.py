"""
URL configuration for rip project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from app import views
from rip import settings

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.index, name='index'),
    path('draft_process', views.draft_process, name='draft-process'),
    path('del-draft', views.del_draft, name='del-draft'),
    path('sending_process/<int:process_id>', views.process, name='sending-process'),
    path('profile/<int:profile_id>', views.profile, name='profile'),
    path('add_to_process/<int:recipient_id>', views.add_to_process, name='add-to-process'),
    path('del_from_process/<int:recipient_id>', views.del_from_process, name='del-from-process')
]

urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_URL)
