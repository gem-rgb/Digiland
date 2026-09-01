Digiland

A structured land verification and safe transaction platform built with Django that reduces avoidable transaction risks through transparent multi-layer verification, documentation auditing, and payment provider confirmation tracking between buyers, sellers, surveyors, advocates, and verified field agents.

---

🏠 Overview

Digiland is a comprehensive land verification and transaction coordination platform designed to make land transactions safer by improving verification, transparency, accountability, and access to trustworthy transaction information. DigiLand does not hold customer funds or maintain custodial escrow balances; payments are processed directly through regulated providers (e.g. M-Pesa, Commercial Banks) while DigiLand maintains immutable audit records, multi-layer verification checks, and milestone progression.

---

🚀 Features

User Roles
- Buyers: Browse pre-screened land parcels, initiate interest-triggered due diligence, track verification milestones
- Sellers: List land parcels, submit ownership documents, manage deals
- Agents & Surveyors: Conduct on-site inspections, boundary & beacon verification, submit field reports
- Advocates & Legal Counsel: Review title deeds, encumbrances, and conveyancing instruments
- Admins: Oversee platform operations, verification reviews, and dispute documentation

Core Functionality
- User Authentication: Email-based authentication with role-based access control
- Identity Verification: KYC verification and multi-factor compliance
- Land Parcel Management: Structured listing, trust profiles, and Controlled Disclosure
- Multi-Layer Verification: 15-milestone transaction tracking across survey, legal, and registry stages
- Payment Records: Audit logs of provider-confirmed transactions (M-Pesa STK, Bank RTGS) without custodial holding
- Dispute Documentation: Structured case tracking and transparent evidence management
- Rating System: Agent performance tracking and user reviews
- Notifications: Automated updates throughout verification and transfer milestones


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
- Server UI: Django Templates with Bootstrap and React shell bootstrap
- Client: React/Tailwind app in `land_escrow/client`
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
├── server/                # Django server app with templates, views, and React bootstrap
│   ├── templates/         # HTML templates
│   ├── views.py           # Server-side views and page bootstrap
│   └── forms.py           # Server-side forms
├── client/                # React client application
│   ├── src/               # React source code
│   └── dist/              # Built assets served by Django
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
-----------
**Local development** uses the console email backend by default — no SMTP
credentials are required.  Verification emails are printed to the runserver
stdout.  Signup and password reset work out of the box.

**Production** forces authenticated SMTP via `settings_production.py`.  To
configure real email delivery, set these in your `.env`:

- `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend`
- `EMAIL_HOST`: Your SMTP server (e.g. `smtp.gmail.com`)
- `EMAIL_PORT`: SMTP port (587 for TLS, 465 for SSL)
- `EMAIL_HOST_USER`: SMTP username
- `EMAIL_HOST_PASSWORD`: SMTP password (use an App Password for Gmail)
- `DEFAULT_FROM_EMAIL`: The "From" address for outgoing emails (independent
  of the SMTP login; falls back to `EMAIL_HOST_USER`, then to
  `noreply@digiland.local`)

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
