'''Production settings for the Django pseudobase project.

These settings are intended to be used when running in a mod_wsgi production
environment.  Settings appropriate for usage in a local development
environment can be found in settings.py.

'''
import os 

DEBUG = True
TEMPLATE_DEBUG = DEBUG

ADMINS = (
  ('Django Admin', 'django@biology.duke.edu'),
)

MANAGERS = (
  ('Django Admin', 'django@biology.duke.edu'),
  ('Mohamed Noor', 'noor@duke.edu'),
)

DATABASES = {
  'default': {
    'ENGINE': 'django.db.backends.mysql',
    'NAME': 'pseudobase',
    'USER': 'root',
    'PASSW  ORD': '',
  }
}
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.sqlite3',
#         'NAME': os.path.join(BASE_DIR, 'pse2_test_db.sqlite3'),
#         #'NAME': 'db.sqlite3'),
#     }
# }

# Hosts/domain names that are valid for this site; required if DEBUG is False
# See https://docs.djangoproject.com/en/1.5/ref/settings/#allowed-hosts
ALLOWED_HOSTS = ['pseudobase.biology.duke.edu']

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# On Unix systems, a value of None will cause Django to use the same
# timezone as the operating system.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = 'America/New_York'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale
USE_L10N = True

# If you set this to False, Django will not use timezone-aware datetimes.
USE_TZ = True

# Absolute filesystem path to the directory that will hold user-uploaded 
# files.
# Example: "/home/media/media.lawrence.com/"
MEDIA_ROOT = 'C:/NewOneDrive/OneDrive - Northgate Information Solutions Limited/Documents/GitLab/pseudobase2/media/'

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash if there is a path component (optional in other cases).
# Examples: "http://media.lawrence.com", "http://example.com/media/"
MEDIA_URL = '/media/'

# Absolute path to the directory static files should be collected to.
# Don't put anything in this directory yourself; store your static files
# in apps' "static/" subdirectories and in STATICFILES_DIRS.
# Example: "/var/www/example.com/static/"
STATIC_ROOT = 'C:/NewOneDrive/OneDrive - Northgate Information Solutions Limited/Documents/GitLab/pseudobase2/staticfiles/'
# URL prefix for static files.
# Example: "http://example.com/static/", "http://static.example.com/"
STATIC_URL = '/static/'

# Additional locations of static files.
STATICFILES_DIRS = (
  'C:/NewOneDrive/OneDrive - Northgate Information Solutions Limited/Documents/GitLab/pseudobase2/static/',
)

# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = (
  'django.contrib.staticfiles.finders.FileSystemFinder',
  'django.contrib.staticfiles.finders.AppDirectoriesFinder',
#  'django.contrib.staticfiles.finders.DefaultStorageFinder',
)

# Make this unique, and don't share it with anybody.
SECRET_KEY = 'kczO$7qauC$$J:82WXtzz<D|g6L-&(GXe)tPgT1;o!K06Ln@%8'

# Use cookie-based sessions.
SESSION_ENGINE = 'django.contrib.sessions.backends.signed_cookies'

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
  'django.template.loaders.filesystem.Loader',
  'django.template.loaders.app_directories.Loader',
  #'django.template.loaders.eggs.Loader',
)

MIDDLEWARE_CLASSES = (
  'django.middleware.gzip.GZipMiddleware',
  'django.middleware.common.CommonMiddleware',
  'django.contrib.sessions.middleware.SessionMiddleware',
  'django.middleware.csrf.CsrfViewMiddleware',
  'django.contrib.auth.middleware.AuthenticationMiddleware',
  'django.contrib.messages.middleware.MessageMiddleware',
  'django.middleware.clickjacking.XFrameOptionsMiddleware',
#  'django_pdb.middleware.PdbMiddleware',
)

ROOT_URLCONF = 'urls'

TEMPLATE_DIRS = (
  # Always use forward slashes, even on Windows.
  # Don't forget to use absolute paths, not relative paths.
  'C:/NewOneDrive/OneDrive - Northgate Information Solutions Limited/Documents/GitLab/pseudobase2/templates',
)

INSTALLED_APPS = (
#  'django_pdb',
  'django.contrib.auth',
  'django.contrib.contenttypes',
  'django.contrib.sessions',
  'django.contrib.sites',
  'django.contrib.messages',
  'django.contrib.staticfiles',
  'django.contrib.admin',
  'south',  
  'common',
  'chromosome',
  'gene',
  # Uncomment the next line to enable admin documentation:
  # 'django.contrib.admindocs',
)

# A sample logging configuration. The only tangible logging
# performed by this configuration is to send an email to
# the site admins on every HTTP 500 error when DEBUG=False.
# See http://docs.djangoproject.com/en/dev/topics/logging for
# more details on how to customize your logging configuration.

# This is fixed in later versions of Django, but we need the following code
# to ignore spurious HTTP Host header "SuspiciousOperation" e-mails.
from django.core.exceptions import SuspiciousOperation

def skip_suspicious_operations(record):
  if record.exc_info:
    exc_value = record.exc_info[1]
    if isinstance(exc_value, SuspiciousOperation):
      return False
  return True

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
        # Define filter
        'skip_suspicious_operations': {
            '()': 'django.utils.log.CallbackFilter',
            'callback': skip_suspicious_operations,
        },
    },
    'handlers': {
        'mail_admins': {
            'level': 'ERROR',
            # Add filter to list of filters
            'filters': ['require_debug_false', 'skip_suspicious_operations'],
            'class': 'django.utils.log.AdminEmailHandler'
        },
        'logfile': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': "C:/NewOneDrive/OneDrive - Northgate Information Solutions Limited/Documents/GitLab/pseudobase2" + "/rbm_logfile.log",
            'maxBytes': 50000,
            'backupCount': 2,
            #'formatter': 'simple',
        },
    },
    'loggers': {
        'django.request': {
            'handlers': ['mail_admins'],
            'level': 'ERROR',
            'propagate': True,
        },
        '': {
            'handlers': ['logfile'],
            'level': 'INFO',
        },
    }
}

# Application-specific settings
PSEUDOBASE_CHROMOSOME_DATA_ROOT = 'C:/NewOneDrive/OneDrive - Northgate Information Solutions Limited/Documents/GitLab/pseudobase2/project_data/pseudobase/chromosome/'
PSEUDOBASE_RESULTS_FILENAME = 'pseudobase_results.zip'
PSEUDOBASE_RESULTS_PREFIX = '/delivery/'
PSEUDOBASE_DELIVERY_ROOT = 'C:/NewOneDrive/OneDrive - Northgate Information Solutions Limited/Documents/GitLab/pseudobase2/project_data/pseudobase/delivery/'

PSEUDOBASE_RAW_DATA_PREFIX = 'raw_data/'
PSEUDOBASE_CHROMOSOME_RAW_DATA_IMPORTED_PREFIX = os.path.join(PSEUDOBASE_RAW_DATA_PREFIX,'chromosome/')
PSEUDOBASE_CHROMOSOME_RAW_DATA_PENDING_PREFIX = os.path.join(PSEUDOBASE_RAW_DATA_PREFIX,'chromosome/pending_import/')


PSEUDOBASE_CHROMOSOME_RAW_DATA_VCF_PREFIX = os.path.join(PSEUDOBASE_RAW_DATA_PREFIX,'chromosome/strain_vcf/')

CURRENT_FLYBASE_RELEASE_VERSION = 'r3.04'
ORIGINAL_RELEASE_VERSION = 'pse1'
