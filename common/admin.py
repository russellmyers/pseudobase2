'''Config of the Django admin interface for the common application.'''

from django.contrib import admin

from common.models import Species, Strain, Chromosome, StrainSymbol


admin.site.register(Species)
admin.site.register(Strain)
admin.site.register(Chromosome)
admin.site.register(StrainSymbol)
