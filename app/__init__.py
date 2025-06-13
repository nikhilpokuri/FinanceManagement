from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail
from datetime import datetime

db = SQLAlchemy()
mail = Mail()

def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_pyfile('config.py')

    db.init_app(app)
    mail.init_app(app)

    from .routes import main
    app.register_blueprint(main)

    # ✅ Context processor to inject current year into all templates
    @app.context_processor
    def inject_current_year():
        return {'current_year': datetime.now().year}

    return app
