'''Config of the Django admin interface for the gene application.'''

from django.contrib import admin

from gene.models import Gene, GeneSymbol, GeneBatchProcess


admin.site.register(Gene)
admin.site.register(GeneSymbol)
admin.site.register(GeneBatchProcess)
