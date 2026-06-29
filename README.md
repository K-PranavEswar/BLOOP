# 🩸 HemoPulse AI Pro

## Intelligent Blood Bank Management, Demand Forecasting & Critical Shortage Prediction System

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Flask](https://img.shields.io/badge/Framework-Flask-green)
![SQLite](https://img.shields.io/badge/Database-SQLite-blue)
![LightGBM](https://img.shields.io/badge/AI-LightGBM-orange)
![Prophet](https://img.shields.io/badge/Forecasting-Meta%20Prophet-purple)
![License](https://img.shields.io/badge/License-MIT-red)

## 📖 Overview

HemoPulse AI Pro is a Flask-based intelligent Blood Bank Management
platform that combines secure user management with AI-powered blood
demand forecasting. The system helps hospitals, blood banks,
administrators, staff, donors, and public users efficiently manage blood
inventory while predicting shortages before they occur.

------------------------------------------------------------------------

# ✨ Features

## 🔐 Authentication

-   Secure Login & Logout
-   User Registration
-   Email OTP Verification
-   Password Hashing using Flask-Bcrypt
-   Forgot Password
-   Session Management
-   Role-Based Access Control

## 👥 User Roles

### Admin

-   Dashboard
-   User Management
-   Staff Approval
-   Blood Inventory
-   AI Reports
-   Notifications
-   Activity Logs

### Staff

-   Inventory Management
-   Blood Request Handling
-   Donation Camp Management
-   AI Prediction Dashboard

### Public User

-   Blood Availability
-   Blood Requests
-   Donor Registration
-   Profile Management
-   Notifications

------------------------------------------------------------------------

# 🤖 AI Modules

-   LightGBM Demand Prediction
-   Meta Prophet Forecasting
-   7-Day Blood Demand Forecast
-   Shortage Prediction
-   Donation Camp Recommendation
-   Inventory Analytics

------------------------------------------------------------------------

# 🛠 Tech Stack

## Backend

-   Python
-   Flask
-   Flask-SQLAlchemy
-   Flask-Login
-   Flask-Bcrypt
-   Flask-Mail

## Frontend

-   HTML5
-   CSS3
-   Bootstrap 5
-   JavaScript
-   Plotly
-   Chart.js

## Machine Learning

-   LightGBM
-   Meta Prophet
-   Scikit-learn
-   Pandas
-   NumPy

## Database

-   SQLite3

# ⚙ Installation

## Clone

``` bash
git clone https://github.com/yourusername/HemoPulse-AI-Pro.git
cd HemoPulse-AI-Pro
```

## Virtual Environment

Windows

``` bash
python -m venv venv
venv\Scripts\activate
```

Linux/macOS

``` bash
python3 -m venv venv
source venv/bin/activate
```

## Install Packages

``` bash
pip install -r requirements.txt
```

------------------------------------------------------------------------

# Environment Variables

Create `.env`

``` env
SECRET_KEY=your-secret-key

DATABASE_URL=sqlite:///hemopulse.db

MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-google-app-password
MAIL_DEFAULT_SENDER=your-email@gmail.com

FLASK_ENV=development
FLASK_DEBUG=1
```

------------------------------------------------------------------------

# Generate Dataset

``` bash
python dataset/synthetic_data_generator.py
```

------------------------------------------------------------------------

# Train Models

``` bash
python src/preprocess.py
python src/train_lightgbm.py
python src/train_prophet.py
python src/evaluate.py
```

------------------------------------------------------------------------

# Run Application

``` bash
python run.py
```

Open

    http://127.0.0.1:5000

------------------------------------------------------------------------

# Default Admin

Username

    admin

Password

    Admin@1234

Change the password after first login.

------------------------------------------------------------------------

# User Workflow

1.  Register
2.  Verify Email using OTP
3.  Login
4.  Staff Approval by Admin
5.  Dashboard Access
6.  Manage Inventory
7.  AI Prediction
8.  Blood Requests
9.  Donation Camp Management

------------------------------------------------------------------------

# Security

-   Password Hashing
-   CSRF Protection
-   Session Security
-   OTP Verification
-   Role Based Access
-   SQL Injection Protection
-   XSS Protection

------------------------------------------------------------------------

# Future Enhancements

-   QR Code Blood Bags
-   Mobile App
-   SMS Gateway
-   AI Retraining
-   REST API
-   Multi Hospital Support
-   Cloud Deployment

------------------------------------------------------------------------

# License

MIT License

© 2026 HemoPulse AI Pro
