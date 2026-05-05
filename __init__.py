from flask import Flask
from flask_mysqldb import MySQL
from flask_wtf.csrf import CSRFProtect

mysql = MySQL()
csrf = CSRFProtect()


def create_app():
    app = Flask(__name__)
    app.config.from_object('config.Config')
    mysql.init_app(app)
    csrf.init_app(app)

    from .routes.main import bp as main_bp
    from .routes.auth import bp as auth_bp
    from .routes.admin import bp as admin_bp
    from .routes.user import user_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(user_bp)

    return app
