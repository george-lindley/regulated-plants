# __init__.py
from flask import Flask, request
from flask_wtf.csrf import CSRFProtect
from app.config import Config
from app.utils.data_manager import DataManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from app.utils.custom_recaptcha import CustomReCaptcha
from app.auth_helpers import account_logged_in, current_account, current_user_is_admin, get_account_store
from app.utils.release_metadata import build_release_metadata


csrf = CSRFProtect()
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)
recaptcha = CustomReCaptcha()

__all__ = ['csrf', 'limiter', 'recaptcha', 'create_app']

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # reCAPTCHA configuration
    app.config['RECAPTCHA_SITE_KEY'] = app.config.get('RECAPTCHA_SITE_KEY')
    app.config['RECAPTCHA_SECRET_KEY'] = app.config.get('RECAPTCHA_SECRET_KEY')
    
    # Initialize extensions
    csrf.init_app(app)
    limiter.init_app(app)
    recaptcha.init_app(app)

    # Data manager (local sample vs remote production)
    data_manager = DataManager.from_app(app)
    data_manager.ensure_ready()
    app.extensions["data_manager"] = data_manager

    if app.config.get("APP_DATABASE_URL"):
        with app.app_context():
            get_account_store()

    @app.before_request
    def refresh_data_cache():
        data_manager.maybe_refresh()

    # Import and register blueprints
    from app.views import home, species, blog, method, api_page, about
    from app.auth_routes import auth
    from app.admin_routes import admin
    app.register_blueprint(home)
    app.register_blueprint(species)
    app.register_blueprint(blog)
    app.register_blueprint(method)
    app.register_blueprint(api_page)
    app.register_blueprint(about)
    app.register_blueprint(auth)
    app.register_blueprint(admin)

    @app.context_processor
    def inject_auth_state():
        account = current_account()
        return {
            "account": account,
            "account_email": account["email"] if account else None,
            "account_logged_in": account_logged_in(),
            "account_is_admin": current_user_is_admin(),
            "release_metadata": build_release_metadata(app),
            "google_analytics_id": app.config.get("GOOGLE_ANALYTICS_ID", ""),
        }

    @app.after_request
    def set_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")

        if request.path.startswith(("/auth", "/admin")):
            response.headers["Cache-Control"] = "no-store"
            response.headers["Pragma"] = "no-cache"

        return response

    return app
