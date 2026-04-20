Digiland

A secure land escrow web application built with Django that facilitates safe land transactions between buyers, sellers, agents, and land officials.

---

🏠 Overview

Digiland is a comprehensive land escrow platform that provides a secure environment for land transactions. The system ensures that all parties involved in land deals are protected through a structured escrow process with identity verification, document management, and payment processing.

---

🚀 Features

User Roles
- Buyers: Browse available land parcels, make offers, and manage transactions
- Sellers: List land parcels, review offers, and manage sales
- Agents: Facilitate transactions, earn commissions, and maintain ratings
- Land Officials: Verify land documents and approve transactions
- Admins: Oversee platform operations and user management

Core Functionality
- User Authentication: Email-based authentication with role-based access control
- Identity Verification: Integration with Gavakonect for KYC verification
- Land Parcel Management: Comprehensive listing and management of land properties
- Document Upload: Secure storage of land titles and related documents via Cloudinary
- Escrow Process: Multi-step transaction workflow with approval stages
- Payment Processing: Paystack integration for secure payment handling
- Rating System: Agent performance tracking and user reviews
- Email Notifications: Automated email updates throughout the transaction process

---

🛠 Tech Stack

Backend
- Framework: Django 6.0.3
- Database: SQLite (development)
- Authentication: Django Allauth
- API: Django REST Framework
- File Storage: Cloudinary (with local fallback)
- Email: SMTP configuration
- Payment: Paystack

Frontend
- Templates: Django Templates with Bootstrap
- UI Components: Widget Tweaks, Slippers
- Static Files: WhiteNoise for production serving

Development Tools
- Environment Management: python-decouple
- Security: Bandit for security scanning
- Dependencies: pip-audit for vulnerability checking

---

📋 Prerequisites

- Python 3.8+
- pip
- virtual environment (recommended)

---

🚀 Installation

1. Clone the repository
   ```bash
   git clone <repository-url>
   cd SCHOOL_PROJECT
   ```

2. Navigate to the project directory
   ```bash
   cd land_escrow
   ```

3. Create and activate virtual environment
   ```bash
   python -m venv venv
   
   # Windows
   venv\Scripts\activate
   
   # Unix/MacOS
   source venv/bin/activate
   ```

4. Install dependencies
   ```bash
   pip install -r requirements.txt
   ```

5. Set up environment variables
   ```bash
   cp env_sample.txt .env
   ```
   Edit the .env file with your configuration:
   - SECRET_KEY: Django secret key
   - DEBUG: Set to False for production
   - EMAIL_HOST, EMAIL_PORT, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD: SMTP settings
   - PAYSTACK_PUBLIC_KEY, PAYSTACK_SECRET_KEY: Paystack API keys
   - CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET: Cloudinary credentials

6. Run database migrations
   ```bash
   python manage.py migrate
   ```

7. Create a superuser
   ```bash
   python manage.py createsuperuser
   ```
   Or use the provided script:
   ```bash
   python create_superuser.py
   ```

8. Collect static files
   ```bash
   python manage.py collectstatic
   ```

9. Run the development server
   ```bash
   python manage.py runserver
   ```

The application will be available at http://127.0.0.1:8000

---

🐳 Docker Deployment

A Dockerfile is provided for containerized deployment:

```bash
# Build the image
docker build -t digiland .

# Run the container
docker run -p 8000:8000 digiland
```

---

📁 Project Structure

```
land_escrow/
├── core/                   # Core application with user models and business logic
│   ├── models.py          # User, Land, Transaction models
│   ├── views.py           # Main business logic views
│   ├── services/          # Business logic services
│   └── middleware.py      # Custom middleware
├── frontend/              # Frontend application with templates and UI
│   ├── templates/         # HTML templates
│   ├── views.py           # UI-specific views
│   └── forms.py           # Frontend forms
├── land_escrow/          # Django project settings
│   ├── settings.py       # Project configuration
│   └── urls.py          # Main URL routing
├── templates/            # Global templates
├── media/               # User-uploaded files (local fallback)
├── static/              # Static files
└── manage.py           # Django management script
```

---

🔧 Configuration

Email Setup
Configure SMTP settings in your .env file for email notifications:
- EMAIL_HOST: Your SMTP server
- EMAIL_PORT: SMTP port (587 for TLS, 465 for SSL)
- EMAIL_HOST_USER: SMTP username
- EMAIL_HOST_PASSWORD: SMTP password
- EMAIL_USE_TLS: Set to True for TLS

Cloudinary Setup (Optional)
For file storage, configure Cloudinary credentials:
- CLOUDINARY_CLOUD_NAME: Your Cloudinary cloud name
- CLOUDINARY_API_KEY: Your Cloudinary API key
- CLOUDINARY_API_SECRET: Your Cloudinary API secret

If not configured, the system will fall back to local file storage.

Paystack Setup
For payment processing:
- PAYSTACK_PUBLIC_KEY: Your Paystack public key
- PAYSTACK_SECRET_KEY: Your Paystack secret key

---

🧪 Testing

The project includes several test scripts for development:

- test_agent_flow.py: Test agent transaction workflows
- test_complete_rejection_flow.py: Test rejection scenarios
- test_email_config.py: Test email configuration
- test_login_flow.py: Test authentication flows

Run tests with:
```bash
python manage.py test
```

---

📝 License

This project is licensed under the Apache License 2.0. See the LICENSE file for details.

---

🤝 Contributing

1. Fork the repository
2. Create a feature branch (git checkout -b feature/AmazingFeature)
3. Commit your changes (git commit -m 'Add some AmazingFeature')
4. Push to the branch (git push origin feature/AmazingFeature)
5. Open a Pull Request

---

🔒 Security

- All user passwords are hashed using Django's default password hashing
- Identity verification through Gavakonect integration
- Secure file storage with Cloudinary
- CSRF protection enabled
- CORS configuration for API security
- Security scanning with Bandit

---

🌟 Key Features Highlight

- Secure Escrow Process: Multi-stage approval workflow ensures safe transactions
- Role-Based Access: Different user types with appropriate permissions
- Document Management: Secure upload and storage of land documents
- Payment Integration: Seamless payment processing with Paystack
- Rating System: Build trust through user ratings and reviews
- Email Notifications: Keep all parties informed throughout the process
- Responsive Design: Mobile-friendly interface for all users
