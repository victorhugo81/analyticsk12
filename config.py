import os
from datetime import timedelta
from dotenv import load_dotenv

# Load environment variables from a .env file
load_dotenv()

class Config:
    # Flask secret key for session management and CSRF protection
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key')  # Fallback for development
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Dedicated key for Fernet encryption of data at rest (user emails, SMTP/FTP
    # credentials) — intentionally NOT SECRET_KEY. Session/CSRF signing and data-at-rest
    # encryption are different trust boundaries; reusing one key for both means a leak of
    # either compromises both, and rotating SECRET_KEY would silently break every stored
    # encrypted value. Generate with:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    DATA_ENCRYPTION_KEY = os.environ.get('DATA_ENCRYPTION_KEY', 'dev-data-key-insecure')

    # Database connection string, with a fallback for development
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///app.db')

    # Recycle MySQL connections before the server-side idle timeout (~8 h)
    SQLALCHEMY_POOL_RECYCLE = 3600

    # Flask-Limiter storage: set RATELIMIT_STORAGE_URI=redis://... in production
    RATELIMIT_STORAGE_URI = os.environ.get('RATELIMIT_STORAGE_URI', 'memory://')

    # Cap upload size at 100 MB to accommodate large attendance/absence exports
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024

    # Sessions expire after 8 hours of inactivity
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)

    # Session cookie security
    SESSION_COOKIE_HTTPONLY = True   # Prevent JavaScript access to session cookie
    SESSION_COOKIE_SAMESITE = 'Lax' # Block cross-site request sending of cookie

    # APScheduler — disable the built-in REST API endpoint
    SCHEDULER_API_ENABLED = False

    # Flask-Mail configuration
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 465))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')


class DevelopmentConfig(Config):
    DEBUG = True  # Enable debug mode for development

class ProductionConfig(Config):
    DEBUG = False  # Disable debug mode for production

    # Secure session cookies in production
    SESSION_COOKIE_SECURE = True      # Only sent over HTTPS
    SESSION_COOKIE_HTTPONLY = True    # Inaccessible to JavaScript
    SESSION_COOKIE_SAMESITE = 'Lax'  # CSRF mitigation

# Dictionary to manage different configurations for different environments.
#
# 'default' maps to ProductionConfig, not DevelopmentConfig — deliberately. Any WSGI
# server that calls create_app() with no argument (a bare `create_app()` factory call,
# which is exactly what `gunicorn -w 4 "main:create_app()"` does if the config name is
# ever omitted from that command) should fail closed into the safer config, not the one
# with DEBUG=True and no SESSION_COOKIE_SECURE. Development must be opted into explicitly
# via `create_app('development')` or `FLASK_ENV=development python main.py`.
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': ProductionConfig,
    'testing': DevelopmentConfig,  # overridden by conftest
}

