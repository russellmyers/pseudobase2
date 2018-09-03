#!/usr/bin/env python

'''Utility script used to manage the pseudobase Django project.

The script attempts to auto-load the appropriate settings based on the
hostname of the server on which it is being executed.  There is probably a
more robust way of handling thing, but it works for the present needs.

'''

import os
import socket
import sys

from django.core.management import execute_from_command_line


production_servers = ['noor-web1.biology.duke.edu']

if __name__ == "__main__":
    if socket.gethostname() in production_servers:
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings_production')
    else:
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

    execute_from_command_line(sys.argv)
