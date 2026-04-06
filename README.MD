# Online Cinema API Service

An online cinema is a digital platform that allows users to select, watch, and purchase access to movies and other video
materials via the internet. These services have become popular due to their convenience, a wide selection of content,
and the ability to personalize the user experience.

## Key Features

- Secure authentication and authorization via JWT  
- Role-based access control (USER / MODERATOR / ADMIN)  
- Movie catalog management  
- Complete shopping cart and order flow  
- Payment system integration Stripe
- Webhook processing 
- Email notifications   
- Docker and Docker Compose support  
- Automated tests with coverage reporting  

## Technical Stack

* **Framework:** FastAPI
* **Asynchronous ORM:** SQLAlchemy
* **Database:** PostgreSQL
* **Payment system Integration:** Stripe 
* **Dependency Management:** Poetry
* **Containerization:** Docker and Docker Compose
* **Testing:** Pytest
* **Documentation:** OpenAPI - Swagger

## **1. Clone the Repository**

Start by cloning the project repository from GitHub:

```bash
git clone <repository-url>
cd <repository-folder>
```

---

## **2. Create and Activate a Virtual Environment**

It is recommended to use a virtual environment to isolate project dependencies:

```bash
# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# On Windows
venv\Scripts\activate
# On macOS/Linux
source venv/bin/activate
```

---

## **3. Install Dependencies with Poetry**

This project uses **Poetry** for dependency management. Install dependencies as follows:

```bash
# Install Poetry if not already installed
pip install poetry

# Install project dependencies
poetry install
```

---

## **4. Create a `.env` File**

Create a `.env` file in the project root directory with the following variables. Customize the values as needed:

```env
# PostgreSQL
POSTGRES_DB=movies_db
POSTGRES_DB_PORT=5432
POSTGRES_USER=admin
POSTGRES_PASSWORD=some_password
POSTGRES_HOST=postgres_theater

# pgAdmin
PGADMIN_DEFAULT_EMAIL=admin@gmail.com
PGADMIN_DEFAULT_PASSWORD=admin

# JWT keys
SECRET_KEY_ACCESS=838qKq7dGp34hWij3c8txA5ZD2qm9ybt
SECRET_KEY_REFRESH=cFzRk8kllHMW71wQKLXBqDzl24fkhisw
JWT_SIGNING_ALGORITHM=HS256

# MailHog
MAILHOG_USER=admin
MAILHOG_PASSWORD=some_password

# Email settings for MailHog
EMAIL_HOST=mailhog_theater
EMAIL_PORT=1025
EMAIL_HOST_USER=testuser@example.com
EMAIL_HOST_PASSWORD=test_password
EMAIL_USE_TLS=False

# MinIO (S3-Compatible Storage)
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=some_password
MINIO_HOST=minio-theater
MINIO_PORT=9000
MINIO_STORAGE=theater-storage

# Stripe
STRIPE_PUBLIC_KEY=test_sapmle_public_key
STRIPE_SECRET_KEY=test_sapmle_secret_key
STRIPE_WEBHOOK_SECRET=test_sapmle_webhook_key
```

---

## **5. Run with Docker**
```bash
docker-compose -f docker-compose-dev.yml up --build
docker-compose -f docker-compose-dev.yml down
```

## Running Tests

Run all tests:

```bash
pytest
```

## API Documentation

Interactive API documentation is available via Swagger UI:
```
http://localhost:8000/docs
```