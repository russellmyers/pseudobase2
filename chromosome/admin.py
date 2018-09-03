'''Config of the Django admin interface for the chromosome application.'''

from django.contrib import admin

from chromosome.models import ChromosomeBase


admin.site.register(ChromosomeBase)
