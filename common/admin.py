'''Config of the Django admin interface for the common application.'''

from django.contrib import admin

from common.models import Species, Strain, Chromosome


admin.site.register(Species)
admin.site.register(Strain)
admin.site.register(Chromosome)
