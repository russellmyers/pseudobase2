'''WSGI config for pseudobase project.

This module contains the WSGI application used by Django's development server
and any production WSGI deployments. It should expose a module-level variable
named ``application``. Django's ``runserver`` and ``runfcgi`` commands discover
this application via the ``WSGI_APPLICATION`` setting.

Usually you will have the standard Django WSGI application here, but it also
might make sense to replace the whole Django WSGI application with a custom one 
that later delegates to the Django one. For example, you could introduce WSGI
middleware here, or combine a Django application with an application of another
framework.

'''
import os
import site
import socket
import sys

from django.core.wsgi import get_wsgi_application


production_servers = ['noor-web1.biology.duke.edu']

# We defer to a DJANGO_SETTINGS_MODULE already in the environment. This breaks
# if running multiple sites in the same mod_wsgi process. To fix this, use 
# mod_wsgi daemon mode with each site in its own daemon process, or use 
# os.environ["DJANGO_SETTINGS_MODULE"] = "foo.settings"
if socket.gethostname() in production_servers:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings_production')
else:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

# Alter the paths if necessary (production).
if socket.gethostname() in production_servers:
    ## Path alteration to support virtualenv and Django projects
    ve_path = '/srv/virtualenv/base/lib/python2.6/site-packages'
    project_path = '/srv/www/projects/pseudobase/'

    prev_sys_path = list(sys.path)

    # Add the site-packages of our virtualenv as a site dir
    site.addsitedir(ve_path)

    # Add the projects directory to the PYTHONPATH
    sys.path.append(project_path)

    # Reorder sys.path so new directories from the addsitedir show up first
    new_sys_path = [p for p in sys.path if p not in prev_sys_path]
    for item in new_sys_path:
        sys.path.remove(item)
    sys.path[:0] = new_sys_path

# This application object is used by any WSGI server configured to use this
# file. This includes Django's development server, if the WSGI_APPLICATION
# setting points here.
application = get_wsgi_application()

# Apply WSGI middleware here.
# from helloworld.wsgi import HelloWorldApplication
# application = HelloWorldApplication(application)
