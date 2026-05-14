from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail
from itsdangerous import URLSafeTimedSerializer
import os

db = SQLAlchemy()
login_manager = LoginManager()
mail = Mail()
# We will initialize serializer in create_app
