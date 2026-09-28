# app/config.py
from dotenv import load_dotenv
import os
from datetime import timedelta

load_dotenv(override=False)

class Config:
   # Secret key for sessions/cookies
   SECRET_KEY = os.getenv('SECRET_KEY', 'dev-only-secret-key-change-me')
   SESSION_COOKIE_HTTPONLY = True
   SESSION_COOKIE_SAMESITE = 'Lax'
   SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', '0').strip().lower() in {
      '1',
      'true',
      'yes',
      'on',
   }
   PERMANENT_SESSION_LIFETIME = timedelta(
      days=int(os.getenv('PERMANENT_SESSION_LIFETIME_DAYS', '90'))
   )
   
   # Database configuration
   DATABASE_PATH = os.getenv('DATABASE_PATH', 'weeds.db')
   
   # Email configuration
   MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER')
   CONTACT_EMAIL = os.getenv('CONTACT_EMAIL') or MAIL_DEFAULT_SENDER
   EMAIL_SEND_TIMEOUT_SECONDS = int(os.getenv('EMAIL_SEND_TIMEOUT_SECONDS', '8'))
   POSTMARK_SERVER_TOKEN = os.getenv('POSTMARK_SERVER_TOKEN')
   POSTMARK_MESSAGE_STREAM = os.getenv('POSTMARK_MESSAGE_STREAM', 'outbound')
   POSTMARK_API_URL = os.getenv('POSTMARK_API_URL', 'https://api.postmarkapp.com/email')

   # reCAPTCHA configuration  
   RECAPTCHA_SITE_KEY = os.environ.get('RECAPTCHA_SITE_KEY')
   RECAPTCHA_SECRET_KEY = os.environ.get('RECAPTCHA_SECRET_KEY')

   # Site configuration
   SITE_NAME = "Regulated Plants Database"
   SITE_AUTHOR = "Regulated Plants Database Team"
   BASE_URL = os.getenv('BASE_URL', 'https://regulatedplants.unu.edu')
   GOOGLE_ANALYTICS_ID = os.getenv('GOOGLE_ANALYTICS_ID', 'G-CFT0DN3EZY')
   OOZR_BASE_URL = os.getenv('OOZR_BASE_URL', '').rstrip('/')
   OOZR_PROJECT_SLUG = os.getenv('OOZR_PROJECT_SLUG', 'regulatedplants')
   OOZR_METRICS_ENABLED = os.getenv('OOZR_METRICS_ENABLED', '0')

   # Account access configuration
   APP_DATABASE_URL = os.getenv('APP_DATABASE_URL', '').strip()
   AUTH_ADMIN_EMAILS = os.getenv('AUTH_ADMIN_EMAILS', '')
   AUTH_TOKEN_MAX_AGE_SECONDS = int(os.getenv('AUTH_TOKEN_MAX_AGE_SECONDS', '1800'))
   AUTH_ANONYMOUS_SAMPLE_LIMIT = int(os.getenv('AUTH_ANONYMOUS_SAMPLE_LIMIT', '5'))
   AUTH_ROR_ENABLED = os.getenv('AUTH_ROR_ENABLED', '1').strip().lower() in {
      '1',
      'true',
      'yes',
      'on',
   }
   AUTH_ROR_ALLOWED_TYPES = os.getenv('AUTH_ROR_ALLOWED_TYPES', 'education,government,facility,healthcare,nonprofit')
   ROR_API_BASE_URL = os.getenv('ROR_API_BASE_URL', 'https://api.ror.org/v2/organizations')
   ROR_API_TIMEOUT_SECONDS = int(os.getenv('ROR_API_TIMEOUT_SECONDS', '4'))

   # GBIF species photo gallery
   GBIF_API_BASE_URL = os.getenv('GBIF_API_BASE_URL', 'https://api.gbif.org/v1')
   GBIF_API_TIMEOUT_SECONDS = int(os.getenv('GBIF_API_TIMEOUT_SECONDS', '8'))
   # GBIF asks integrators to put a contact URL or email in the User-Agent so they
   # can reach us about problem traffic rather than just blocking the app. Kept
   # separate from CONTACT_EMAIL (the contact-form recipient) so the address is
   # always present, even where mail is unconfigured.
   GBIF_CONTACT_EMAIL = os.getenv('GBIF_CONTACT_EMAIL', 'lindley@menacon.com')
   GBIF_API_USER_AGENT = os.getenv('GBIF_API_USER_AGENT') or (
      f"regulated-plants-app/1.0 (+{BASE_URL}"
      + (f"; mailto:{GBIF_CONTACT_EMAIL}" if GBIF_CONTACT_EMAIL else "")
      + ")"
   )
   # 5 tiles fill the featured gallery layout exactly (one 2x2 + four 1x1).
   GBIF_PHOTO_LIMIT = int(os.getenv('GBIF_PHOTO_LIMIT', '5'))
   GBIF_PHOTO_CACHE_TTL_SECONDS = int(os.getenv('GBIF_PHOTO_CACHE_TTL_SECONDS', '86400'))
   GBIF_PHOTOS_ENABLED = os.getenv('GBIF_PHOTOS_ENABLED', '1').strip().lower() in {
      '1',
      'true',
      'yes',
      'on',
   }
   AUTH_DEV_SHOW_MAGIC_LINK = os.getenv('AUTH_DEV_SHOW_MAGIC_LINK', '0').strip().lower() in {
      '1',
      'true',
      'yes',
      'on',
   }

   # Highlights override (single country name; optional)
   LATEST_COUNTRY_NAME = os.getenv('LATEST_COUNTRY_NAME', 'South Africa')

   # Development vs Production
   DEBUG = os.getenv('FLASK_DEBUG', False)
   
   # Cache settings
   SEND_FILE_MAX_AGE_DEFAULT = 0
   CACHE_CONTROL = 'no-store, no-cache, must-revalidate'
   PRAGMA = 'no-cache'
   EXPIRES = '-1'
   GEOJSON_CACHE_MAX_AGE_SECONDS = int(os.getenv('GEOJSON_CACHE_MAX_AGE_SECONDS', '31536000'))

   # Data service configuration
   DATA_MODE = os.getenv('DATA_MODE', 'local_sample')
   DATA_REMOTE_BASE_URL = os.getenv('DATA_REMOTE_BASE_URL')
   DATA_REMOTE_TOKEN = os.getenv('DATA_REMOTE_TOKEN')
   DATA_MANIFEST_PATH = os.getenv('DATA_MANIFEST_PATH', '/manifest.json')
   DATA_MANIFEST_TTL_SECONDS = int(os.getenv('DATA_MANIFEST_TTL_SECONDS', '0'))
   DATA_CACHE_DIR = os.getenv('DATA_CACHE_DIR', 'data_cache')
   DATA_REMOTE_TIMEOUT_SECONDS = int(os.getenv('DATA_REMOTE_TIMEOUT_SECONDS', '90'))
   LOCAL_SAMPLE_DB_PATH = os.getenv(
      'LOCAL_SAMPLE_DB_PATH',
      os.path.join('app', 'static', 'data', 'sample', 'weeds_sample.db')
   )
   LOCAL_SAMPLE_GEOJSON_DIR = os.getenv(
      'LOCAL_SAMPLE_GEOJSON_DIR',
      os.path.join('app', 'static', 'data', 'sample', 'geojson')
   )
   
   # Directory paths
   BLOG_DIR = "app/blog_posts"

   API_OPENAPI_PATH = os.getenv(
      'API_OPENAPI_PATH',
      os.path.join('app', 'static', 'data', 'openapi.json')
   )
   # Blog settings
   POSTS_PER_PAGE = 10
