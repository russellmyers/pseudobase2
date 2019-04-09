'''Config of the Django admin interface for the chromosome application.'''

from django.contrib import admin

from chromosome.models import ChromosomeBase, ChromosomeImportLog, ChromosomeBatchImportLog, ChromosomeBatchImportProcess


admin.site.register(ChromosomeBase)
admin.site.register(ChromosomeBatchImportProcess)
admin.site.register(ChromosomeImportLog)
admin.site.register(ChromosomeBatchImportLog)

