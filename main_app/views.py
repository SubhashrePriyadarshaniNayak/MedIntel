import json
from django.http import JsonResponse
from django.shortcuts import redirect, render, get_object_or_404
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django import forms
from django.db import models, transaction
from xhtml2pdf import pisa
from main_app.models import APPOINTMENT_STATUS_OPTIONS, Doctor, Address, Patient, Appointment, Prescription, Visit
from django.contrib.auth import update_session_auth_hash
from django.core.paginator import Paginator

from django.http import HttpResponse
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
import os
import io
from django.template.loader import get_template
from datetime import date

from medintel import settings
from django.views.decorators.csrf import csrf_exempt
from together import Together


# Create your views here.

# Home view
def home(request):
    return render(request,'homepage/index.html')

# Our Doctors View
def our_docts(request):
    # Get search queries from GET request
    doctor_name = request.GET.get('doctor-name', '').strip()
    specialization = request.GET.get('specialization', '').strip()
    locality = request.GET.get('locality', '').strip()
    
    doctors = Doctor.objects.filter(status='Approved')

    if doctor_name:
        doctors = doctors.filter(
            models.Q(user__first_name__icontains=doctor_name) | 
            models.Q(user__last_name__icontains=doctor_name)
        )

    if specialization:
        doctors = doctors.filter(specialization__icontains=specialization)

    if locality:
        doctors = doctors.filter(
            models.Q(prac_address__locality__icontains=locality) |
            models.Q(prac_address__address_line_one__icontains=locality) |
            models.Q(prac_address__city__icontains=locality) |
            models.Q(prac_address__state__icontains=locality) |
            models.Q(prac_address__country__icontains=locality)
        )

    doctors_found = doctors.exists()

    return render(request, 'homepage/our_doctors.html', {
        'doctors': doctors,
        'doctorname': doctor_name,
        'specialization': specialization,
        'locality': locality,
        'doctors_found': doctors_found,
    })

# Doctor UI
@login_required(login_url='accounts:signin_doctor')
def doctor_ui(request):
    doctor = getattr(request.user, 'doctor', None)
    if not doctor:
        messages.error(request, 'You are not logged in as a doctor.')
        return redirect('accounts:signin_doctor')

    # Handle form submission for updating individual appointment status and notes
    if request.method == "POST":
        # Handle the submission of each appointment's note and status
        for appointment in Appointment.objects.filter(doctor=doctor):
            note_key = f"note_{appointment.id}"
            status_key = f"status_{appointment.id}"

            updated = False

            # Update the note for this appointment
            note_value = request.POST.get(note_key)
            if note_value:
                appointment.note = note_value
                updated = True

            # Update the status for this appointment
            status_value = request.POST.get(status_key)
            valid_statuses = [k for k, v in APPOINTMENT_STATUS_OPTIONS]
            if status_value in valid_statuses:
                appointment.status = status_value
                updated = True

            if updated:
                appointment.save()

        messages.success(request, "Appointments updated successfully.")

    # Fetch doctor's appointments to display in the template
    appointments = Appointment.objects.filter(doctor=doctor)

    return render(request, 'doctor/index.html', {
        'doctor': doctor,
        'appointments': appointments,
        'APPOINTMENT_STATUS_OPTIONS': APPOINTMENT_STATUS_OPTIONS  # Pass status options to template
    })

# Patient UI
def patient_ui(request):
    user_id = request.session.get('user_id', None)
    if user_id is None:
        messages.error(request, 'You are not logged in as a patient.')
        return redirect('accounts:signin_patient')

    user = get_object_or_404(User, id=user_id)

    # ✅ Check if user has a related patient object
    patient = getattr(user, 'patient', None)  
    if patient is None:
        messages.error(request, 'You do not have a patient profile.')
        return redirect('home')  # Redirect to home or another appropriate page

    # ✅ Fetch visits and appointments
    visits = Visit.objects.filter(patient=patient) if patient else []
    appointments = Appointment.objects.filter(user=user)  # Fetch appointments

    # Get all doctors from prescriptions
    doctors = Doctor.objects.filter(prescription__patient=patient).distinct()
    doctor_id = request.GET.get('doctor')

    previous_prescriptions = Prescription.objects.filter(patient=patient)
    if doctor_id:
        previous_prescriptions = previous_prescriptions.filter(doctor_id=doctor_id)

    previous_prescriptions = previous_prescriptions.order_by('-appointment__date')

    # Pagination
    paginator = Paginator(previous_prescriptions, 5)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Handle AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            "prescriptions_html": render(request, 'patient/prescription_list.html', {"previous_prescriptions": page_obj}).content.decode('utf-8')
        })

    return render(request, 'patient/index.html', {
        'patient': patient,
        'visits': visits,
        'appointments': appointments,
        'previous_prescriptions' : page_obj,
        'doctors' : doctors
    })


# Update address
@login_required
def update_address(request):
    if request.method == 'POST':
        # Get the form data
        address_line_one = request.POST.get('address_line_one')
        locality = request.POST.get('locality')
        city = request.POST.get('city')
        state = request.POST.get('state')
        country = request.POST.get('country')

        # Create or update the address
        address, created = Address.objects.update_or_create(
            address_line_one=address_line_one,
            locality=locality,
            city=city,
            state=state,
            country=country
        )

        # Update the doctor's practice address if it's the logged-in doctor
        doctor = Doctor.objects.get(user=request.user)
        doctor.prac_address = address
        doctor.save()

        return redirect('doctor_ui')

    messages.error(request, 'Invalid request.')
    return redirect('doctor_ui')


# @login_required(login_url='accounts/signin_patient')
# def profile(request):
#     patient = Patient.objects.filter(patient=request.user).first()  # Get patient safely

#     visits = Visit.objects.filter(patient=patient) if patient else []  # Fetch visits if patient exists
#     appointments = Appointment.objects.filter(user=request.user)  # Fetch appointments

#     context = {
#         'patient': patient,
#         'visits': visits,
#         'appointments': appointments,  # Include appointments in context
#     }

#     return render(request, 'patient/index.html', context)

@login_required(login_url='/accounts/signin_patient/')
def appointment(request, doctor_id):
    doctor = get_object_or_404(Doctor, id=doctor_id)

    if request.method == 'POST':
        mobile = request.POST.get('mobile')
        date = request.POST.get('date')
        note = request.POST.get('note')

        if Appointment.objects.filter(user=request.user, date=date, doctor=doctor).exists():
            messages.error(request, f"Appointment for {date} with Dr. {doctor.user.username} is already booked.")
        elif Appointment.objects.filter(date=date, doctor=doctor).count() >= 20:
            messages.error(request, f"All slots for {date} with Dr. {doctor.name} are booked.")
        else:
            appointment = Appointment(user=request.user, doctor=doctor, mobile=mobile, date=date, note=note)
            appointment.save()
            messages.success(request, f"Appointment booked with Dr. {doctor.user.username}")

    # Fetch only the logged-in user's appointments with this doctor
    appointments = Appointment.objects.filter(user=request.user, doctor=doctor)

    context = {
        'appointments': appointments,
        'doctor': doctor
    }
    return render(request, 'patient/appointment.html', context)

def appointment_details(request, aid):
    if request.method == 'GET':
        try:
            app = Appointment.objects.get(id=aid)
            patient = Patient.objects.get(patient=app.user)
            doctor = app.doctor  # Fetch doctor from appointment
            
            try:
                prescription = Prescription.objects.get(appointment=app)
            except Prescription.DoesNotExist:
                prescription = None

            previous_prescriptions = Prescription.objects.filter(
                patient=patient,
                appointment__date__lt=app.date
            ).order_by('-appointment__date')

            context = {
                'appointment': app,
                'patient': patient,
                'doctor': doctor,  # Add doctor in context
                'prescription': prescription,
                'previous_prescriptions': previous_prescriptions
            }

            if hasattr(request.user, 'doctor'):
                return render(request, 'doctor/appointment_details.html', context)
            else:
                return render(request, 'patient/appointment_details.html', context)
        
        except Appointment.DoesNotExist:
            messages.error(request, "Appointment not found!")
            return redirect('doctor_ui')

        
def add_prescription(request, aid):
    appointment = get_object_or_404(Appointment, id=aid)
    if appointment:
        patient = Patient.objects.get(patient=appointment.user)

    # Check if a prescription already exists
    prescription, created = Prescription.objects.get_or_create(
        appointment=appointment,
        defaults={'patient': patient, 'doctor': appointment.doctor}
    )

    if request.method == "POST":
        medications_json = request.POST.get("medications_json", "[]")  # Retrieve JSON string

        try:
            medications = json.loads(medications_json)  # Convert to Python list
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid medications data"}, status=400)

        # Save prescription
        prescription.medications = medications
        prescription.save()

        return redirect('appointment_details', aid=appointment.id)  # Redirect to appointment page

    context = {
        'appointment': appointment,
        'patient' : patient
    }

    return render(request, 'doctor/appointment_details.html', context)

def generate_prescription_pdf(request, prescription_id):
    # Fetch the prescription details
    prescription = get_object_or_404(Prescription, id=prescription_id)
    patient = prescription.patient
    doctor = prescription.doctor

    # Render HTML template with context
    template = get_template('patient/prescription_template.html')
    html_content = template.render({
        'prescription': prescription,
        'patient': patient,
        'doctor': doctor,
    })

    # Create a BytesIO buffer to receive PDF output
    buffer = io.BytesIO()
    pisa_status = pisa.CreatePDF(html_content, dest=buffer)

    if pisa_status.err:
        return HttpResponse("Error creating PDF", content_type='text/plain')

    # Return response as a downloadable PDF file
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Prescription_{prescription_id}.pdf"'
    return response

@login_required(login_url='accounts:signin_patient')
def delete_appointment(request, aid):
    try:
        app = Appointment.objects.get(id=aid)

        # Ensure only the user who booked it can delete
        if app.user == request.user:
            app.delete()
            messages.success(request, "Appointment Deleted")
        else:
            messages.error(request, "Unauthorized action!")
    except Appointment.DoesNotExist:
        messages.error(request, "Appointment not found!")

    return redirect('appointment', doctor_id=app.doctor.id)



@login_required(login_url='accounts:signin_patient')
def update_appointment(request, aid):
    try:
        appointment = Appointment.objects.get(id=aid)

        # Ensure only the user who booked it can update
        if appointment.user != request.user:
            messages.error(request, "Unauthorized action!")
            return redirect('appointment', doctor_id=appointment.doctor.id)

        if request.method == 'POST':
            mobile = request.POST.get('mobile')
            date = request.POST.get('date')
            note = request.POST.get('note')

            if Appointment.objects.filter(user=request.user, date=date, doctor=appointment.doctor).exclude(id=aid).exists():
                messages.error(request, f"Appointment for {date} with Dr. {appointment.doctor.name} is already booked.")
            elif Appointment.objects.filter(date=date, doctor=appointment.doctor).count() >= 20:
                messages.error(request, f"All slots for {date} with Dr. {appointment.doctor.name} are booked.")
            else:
                # Update only modified fields
                appointment.mobile = mobile
                appointment.date = date
                appointment.note = note
                appointment.save()
                messages.success(request, "Appointment Updated")
                return redirect('appointment', doctor_id=appointment.doctor.id)

        context = {
            'appointment': appointment
        }
        return render(request, 'patient/appointment_update.html', context)

    except Appointment.DoesNotExist:
        messages.error(request, "Appointment not found!")
        return redirect('home')
    
class EmailChangeForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['email']

@login_required
def email_update(request):
    if request.method == "POST":
        email_form = EmailChangeForm(request.POST, instance=request.user)
        if email_form.is_valid():
            email_form.save()
            messages.success(request, "Email Updated Successfully")

            # Redirect based on user type
            if hasattr(request.user, 'patient'):  
                return redirect('patient_ui')
            elif hasattr(request.user, 'doctor'):
                return redirect('doctor_ui')
            else:
                return redirect('home')

    else:
        email_form = EmailChangeForm(instance=request.user)

    # Render the appropriate template based on user type
    if hasattr(request.user, 'doctor'):  
        return render(request, 'doctor/email_update.html', {'email_form': email_form})
    else:
        return render(request, 'patient/email_update.html', {'email_form': email_form})

# @login_required
# def password_update(request):
#     if request.method == "POST":
#         password_form = PasswordChangeForm(request.user, request.POST)
#         if password_form.is_valid():
#             password_form.save()
#             update_session_auth_hash(request, request.user)  # Keeps the user logged in after password change
#             messages.success(request, "Password Updated Successfully")

#             # Redirect based on user type
#             if hasattr(request.user, 'patient'):  
#                 return redirect('patient_ui')
#             elif hasattr(request.user, 'doctor'):
#                 return redirect('doctor_ui')
#             else:
#                 return redirect('home')
#     else:
#         password_form = PasswordChangeForm(request.user)

@login_required
def password_update(request):
    if request.method == "POST":
        old_password = request.POST.get("old_password")
        new_password1 = request.POST.get("new_password1")
        new_password2 = request.POST.get("new_password2")

        if not request.user.check_password(old_password):
            messages.error(request, "Old password is incorrect.")
        elif new_password1 != new_password2:
            messages.error(request, "New passwords do not match.")
        else:
            request.user.set_password(new_password1)
            request.user.save()
            update_session_auth_hash(request, request.user)
            messages.success(request, "Password Updated Successfully")

            # Redirect based on user type
            return redirect("doctor_ui" if hasattr(request.user, "doctor") else "patient_ui")

    # Render the appropriate template
    template = "doctor/password_update.html" if hasattr(request.user, "doctor") else "patient/password_update.html"
    return render(request, template)


    # Render the appropriate template based on user type
    # if hasattr(request.user, 'doctor'):  
    #     return render(request, 'doctor/password_update.html', {'password_form': password_form})
    # else:
    #     return render(request, 'patient/password_update.html', {'password_form': password_form})


# Chatbot View

API_KEY = settings.TOGETHER_API_KEY
client = Together(api_key=API_KEY)
LAST_CONVO = {}

@csrf_exempt
def chatbot_response(request):
    session_id = request.session.session_key
    if not session_id:
        request.session.create()
        session_id = request.session.session_key
    
    if request.method == "POST":
        data = json.loads(request.body)
        user_input = data.get("query", "").strip()

        if not user_input:
            return JsonResponse({"response": "Please enter a medical question."})

        previous_response = LAST_CONVO.get(session_id, "")

        messages = [
            {"role": "system", "content": "You are MedAI, an AI medical assistant designed to provide general health guidance in a clear, professional, and responsible manner.\n\n✅ You can:\n- Answer questions about **common medical conditions, symptoms, prevention strategies, and general wellness**.\n- Keep responses **concise (within 100 words)**, avoiding unnecessary complexity.\n\n🚫 You **cannot**:\n- Provide **personal diagnoses, treatment plans, or prescriptions**. Instead, always recommend consulting a doctor.\n- Respond to **emergency situations**—instead, instruct the user to seek urgent medical attention.\n- Answer **non-medical questions** (e.g., finance, sports, technology). Politely state that you specialize in medical topics.\n\n🔹 **Prevent self-medication.**\n🔹 **Correct misinformation about health.**"}
        ]

        # Add previous response only if it exists
        if previous_response:
            messages.append({"role": "assistant", "content": previous_response})

        # Add the new user query
        messages.append({"role": "user", "content": user_input})

        # Call the AI model
        stream = client.chat.completions.create(
            model="meta-llama/Llama-3.3-70B-Instruct-Turbo-Free",
            max_tokens=200,  # Ensures concise responses
            messages=messages,
            stream=True,
        )

        response_text = ""
        for chunk in stream:
            response_text += chunk.choices[0].delta.content or ""

        LAST_CONVO[session_id] = response_text

        return JsonResponse({"response": response_text})

    return JsonResponse({"response": "Invalid request"}, status=400)

# prediction model starts here
import json
import numpy as np
import pickle


with open("./disease_pred/vectorizer.pkl","rb") as file:
    vectorizer = pickle.load(file)

with open("./disease_pred/label_encoder.pkl","rb") as file:
    le = pickle.load(file)

with open("./disease_pred/symptoms.json", "r") as file:
    symptoms = json.load(file)

with open("./disease_pred/disease_prediction_model.pkl","rb") as file:
    model = pickle.load(file)

with open("./disease_pred/disease_data.json", "r") as file:
    diseases = json.load(file)



def predictor(request):
    input_arr = []
    # if request.method == "GET": 
        # return render(request , 'predictDisease/predictionUi.html')
    if request.method == "POST":
        Name = request.POST.get("patientname")
        symptomlist = request.POST.get("selectedSymptoms")
        x = symptomlist.split(",")
        # print(x)
        for symptom in x:
            if symptom.strip() in symptoms:
                input_arr.append(symptom.strip())

        # print(input_arr)

        result = predict_disease(input_arr)

        predicted_doctor = diseases[result]

        return render(request, 'predictDisease/predictionUi.html', {'predictions': result , 'doctors': predicted_doctor, 'symptoms': input_arr})

    return render(request , 'predictDisease/predictionUi.html')   

def predict_disease(symptoms):
    cleaned = ' '.join(symptoms)
    tfidf = vectorizer.transform([cleaned])
    pred = model.predict(tfidf)
    return le.inverse_transform(pred)[0]

