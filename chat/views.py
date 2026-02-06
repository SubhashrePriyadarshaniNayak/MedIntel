from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import Message
from main_app.models import Appointment

@login_required
def chat_room(request, doctor_username):
    user1 = doctor_username
    user2 = request.user.username

    # Always sort usernames to avoid mismatch
    room_name = f'{min(user1, user2)}_{max(user1, user2)}'

    messages = Message.objects.filter(room_name=room_name).order_by('timestamp')

    return render(request, 'chat/chat_room.html', {
        'room_name': room_name,
        'messages': messages
    })

@login_required
def doctor_chat_list(request):
    doctor = request.user.doctor
    appointments = Appointment.objects.filter(doctor=doctor, status='Visited')

    context = {
        'appointments': appointments
    }
    return render(request, 'chat/doctor_chat_list.html', context)