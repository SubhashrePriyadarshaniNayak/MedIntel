from django.urls import path
from . import views

urlpatterns = [
    path('<str:doctor_username>/', views.chat_room, name='chat_room'),
    path('doctor/chats/', views.doctor_chat_list, name='doctor_chat_list'),
]