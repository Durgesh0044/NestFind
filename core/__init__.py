import os
from flask import Flask
from dotenv import load_dotenv

from core.extensions import db, login_manager, mail
from core.models import Broker

def create_app(test_config=None):
    load_dotenv()
    
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    app = Flask(
        __name__,
        static_folder=os.path.join(BASE_DIR, "static"),
        template_folder=os.path.join(BASE_DIR, "templates"),
    )

    # File upload configuration
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    # Database configuration
    try:
        DB_HOST = os.getenv("DB_HOST")
        DB_PORT = os.getenv("DB_PORT")
        DB_NAME = os.getenv("DB_NAME")
        DB_USER = os.getenv("DB_USER")
        DB_PASSWORD = os.getenv("DB_PASSWORD")
        
        if all([DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD]):
            DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
            print(f"Using PostgreSQL database: {DB_HOST}:{DB_PORT}/{DB_NAME}")
        else:
            raise ValueError("Missing database environment variables")
            
    except Exception as e:
        print(f"Warning: PostgreSQL configuration issue: {e}")
        print("Falling back to SQLite database for testing")
        DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'database.db')}"

    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "nestfind_secret_key_123")

    # Mail configuration
    app.config['MAIL_SERVER'] = os.getenv('MAIL_HOST', 'smtp.gmail.com')
    app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
    app.config['MAIL_USE_TLS'] = os.getenv('MAIL_ENCRYPTION', 'tls').lower() == 'tls'
    app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
    
    from_address = os.getenv('MAIL_FROM_ADDRESS', os.getenv('MAIL_USERNAME', '')).strip('"').strip("'")
    from_name = os.getenv('MAIL_FROM_NAME', 'NestFind').strip('"').strip("'")
    app.config['MAIL_DEFAULT_SENDER'] = (from_name, from_address)

    # Initialize extensions
    db.init_app(app)
    mail.init_app(app)
    
    login_manager.init_app(app)
    login_manager.login_view = 'auth.signin'
    
    @login_manager.user_loader
    def load_user(user_id):
        return Broker.query.get(int(user_id))

    # Register Blueprints
    from core.routes.auth import auth_bp
    from core.routes.public import public_bp
    from core.routes.admin import admin_bp
    from core.routes.superadmin import superadmin_bp
    from core.routes.api import api_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(public_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(superadmin_bp)
    app.register_blueprint(api_bp)

    return app
