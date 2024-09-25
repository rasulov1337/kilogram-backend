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
    path('transfer/<int:process_id>', views.transfer, name='transfer'),
    path('del-transfer/<int:process_id>', views.del_transfer, name='del-transfer'),
    path('profile/<int:profile_id>', views.profile, name='profile'),
    path('add_to_transfer/<int:recipient_id>', views.add_to_transfer, name='add-to-transfer'),
]

urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_URL)
