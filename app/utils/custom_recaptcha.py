# app/utils/custom_recaptcha.py
"""
Simple custom reCAPTCHA implementation without Flask-ReCaptcha
"""
import requests
from flask import request, current_app
from markupsafe import Markup  # Only import from markupsafe, not from flask

class CustomReCaptcha:
    """A simple reCAPTCHA implementation that doesn't rely on Flask-ReCaptcha"""
    
    def __init__(self, app=None, site_key=None, secret_key=None, **kwargs):
        self.site_key = site_key
        self.secret_key = secret_key
        self.options = kwargs
        
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize with a Flask application"""
        self.site_key = app.config.get('RECAPTCHA_SITE_KEY', self.site_key)
        self.secret_key = app.config.get('RECAPTCHA_SECRET_KEY', self.secret_key)
        
        # Add to Jinja2 globals
        app.jinja_env.globals['recaptcha'] = self.get_code()
    
    def get_code(self):
        """Returns the HTML code for the reCAPTCHA widget"""
        try:
            html = """
            <script src='https://www.google.com/recaptcha/api.js'></script>
            <div class="g-recaptcha" data-sitekey="{SITE_KEY}"></div>
            """.format(SITE_KEY=self.site_key)
            return Markup(html)
        except Exception as e:
            # In case of any error, return an empty string
            print(f"Error generating reCAPTCHA code: {e}")
            return ""
    
    def verify(self):
        """Verifies the reCAPTCHA response"""
        if not self.secret_key:
            # Allow local bypass only when DEBUG is explicitly True; fail closed otherwise.
            if current_app.config.get("DEBUG") is True:
                current_app.logger.warning("RECAPTCHA_SECRET_KEY missing; bypassing verification in debug mode.")
                return True
            current_app.logger.error("RECAPTCHA_SECRET_KEY missing; denying reCAPTCHA verification.")
            return False
            
        data = {
            'secret': self.secret_key,
            'response': request.form.get('g-recaptcha-response', '')
        }
        
        try:
            response = requests.post(
                'https://www.google.com/recaptcha/api/siteverify',
                data=data
            )
            result = response.json()
            return result.get('success', False)
        except Exception as e:
            # On error, fail closed (return False)
            print(f"Error verifying reCAPTCHA: {e}")
            return False
