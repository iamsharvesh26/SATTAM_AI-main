# 🧠 SATTAM AI – Legal Assistance Platform

## 📌 Overview

SATTAM AI is a modular legal assistance platform designed to provide intelligent legal services through multiple backend modules and a Flutter-based frontend.

The system is built using a **microservices-inspired architecture**, where each backend module handles a specific domain, ensuring scalability, maintainability, and separation of concerns.

---

## 🏗️ Project Structure

```
SATTAM_AI/
├── legal_ai_backend/              # Chatbot / core AI backend
├── sattam_feed_backend/           # Legal news & case feed system
├── legal_drafting_backend/        # Legal drafting & document generation
├── sattam_gamification_backend/   # Gamification & user engagement
└── frontend/
    └── sattam_ai/                 # Flutter mobile application
```

---

## ⚙️ Backend Modules

### 🔹 1. Legal AI Backend

* Handles chatbot interactions
* Processes legal queries
* Provides intelligent responses

### 🔹 2. Feed Backend

* Fetches legal news and case updates
* Provides personalized content feeds
* Supports ingestion and scraping services

### 🔹 3. Legal Drafting Backend

* Generates legal documents
* Supports templates and clause generation
* Includes document simplification features

### 🔹 4. Gamification Backend

* Tracks user activity
* Implements rewards and engagement logic
* Enhances user interaction with the platform

---

## 📱 Frontend (Flutter)

* Built using **Flutter**
* Provides user interface for all backend services
* Features:

  * Chat interface
  * Document drafting UI
  * Feed display
  * User interaction modules

---

## 🔄 How It Works

1. User interacts via Flutter app
2. Requests are sent to respective backend modules
3. Backend processes data and returns response
4. Frontend displays results to the user

---

## 🚀 Setup Instructions

### 🔧 Backend (for each module)

```bash
cd <module_name>
pip install -r requirements.txt
python app/main.py
```

---

### 📱 Frontend (Flutter)

```bash
cd frontend/sattam_ai
flutter pub get
flutter run
```

---

## 🔐 Security Practices

* Sensitive files like `google-services.json` are excluded using `.gitignore`
* Environment-specific configurations are not pushed to GitHub

---

## 🧠 Architecture

* Modular backend design
* Separation of concerns
* Scalable and maintainable system
* Frontend decoupled from backend services

---

## 🎯 Key Features

* AI-powered legal chatbot
* Automated legal drafting
* Real-time legal news feed
* Gamified user experience
* Cross-platform mobile app

---

## 👨‍💻 Tech Stack

* **Backend:** Python (FastAPI)
* **Frontend:** Flutter
* **Database:** (Add yours if needed)
* **Tools:** Git, VS Code

---

## 🎓 Academic Context

This project was developed as part of a college assignment to demonstrate:

* Full-stack development
* Modular system design
* API integration
* Real-world application architecture

---

## 📌 Future Enhancements

* Authentication & user management
* Cloud deployment
* Advanced AI models
* Real-time notifications

---

## 🙌 Conclusion

SATTAM AI demonstrates a scalable and modular approach to building intelligent legal systems, combining AI, backend services, and mobile application development into a unified platform.
