# MedIntel

MedIntel is an AI-augmented healthcare system that leverages machine learning to streamline healthcare by providing intelligent symptom analysis and preliminary diagnosis. It enhances doctor-patient interaction, reduces diagnostic time, and supports remote medical consultation. The system integrates a chatbot interface, a disease prediction model and appointment management for improved communication and accessibility.

## 🚀 Key Features

- Real-time doctor-patient chat using WebSockets
- Location-based specialist searching
- Simple appointment booking system
- Interactive chatbot interface for user engagement
- AI-powered symptom checker and diagnosis
- Medical history persistence through prescription management

## 🌐 Technologies

- Frontend: HTML, Tailwind CSS, JS
- Backend: Python, Django, Django Channels
- API: Together API
- Chat Model: Llama 3.3 Turbo Instruct Free
- Database: Sqlite3
- ASGI Server - Daphne

## 📦 Project Setup

Follow these steps to set up the project locally:

### 1. 📁 Download the Project

- Clone or download the ZIP file from the repository.

If downloading the ZIP:
- Extract the contents to a desired directory on your system.

### 2. 🐍 Set Up a Virtual Environment

Open a terminal in the project directory and run:

```bash
python -m venv venv
venv/Scripts/activate  # cmd
```

### 3. 📜 Install Requirements

Install all required Python packages using:

```bash
pip install -r requirements.txt
```

### 4. ⚙️ Run Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### 5. 🌐 Run the Daphne ASGI Server

Start the application with:

```bash
daphne medintel.asgi:application
```

The server will typically run on port `8000`. Open your browser and navigate to:

```bash
http://127.0.0.1:8000/
```

## 🌍 Timezone Settings

The project uses Indian Standard Time (IST):

```python
TIME_ZONE = 'Asia/Kolkata'