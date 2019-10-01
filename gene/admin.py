'''Config of the Django admin interface for the gene application.'''

from django.contrib import admin

from gene.models import Gene, GeneSymbol, GeneBatchProcess, MRNA, CDS, GeneImportLog, GeneSymbolImportLog


admin.site.register(Gene)
admin.site.register(GeneSymbol)
admin.site.register(GeneBatchProcess)
admin.site.register(MRNA)
admin.site.register(CDS)
admin.site.register(GeneImportLog)
admin.site.register(GeneSymbolImportLog)
