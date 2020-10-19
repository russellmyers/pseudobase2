'''A custom Django administrative command for importing gene symbols.

This command imports additional symbols (ie once initial symbols have  already been imported using gene_symbol_import)

File format (tab separated) is:
symbol  dpse_FBgn_ID (where dpse_FBgn_ID is the related Dpse FBgnID which is already expected to be present in the gene symbol table)

eg
symbol  dpse_FBgnID
GL16052  FBgn0070102
Dmel_FBgn0035724 FBgn0070102
Dper_FBgn0152666 FBgn0070102


Note: FBgn IDs for species other than Dpse need to have species prepended, eg Dmel_FBgn0035724, Dper_FBgn0152666 etc.
ie only Dpse FBgn Ids themselves should commence with "FBgn.."
'''

import csv
import os
import re
import sys

import django.utils.timezone
from django.core.management.base import BaseCommand
from django.db import connection, transaction

from common.models import Strain, Chromosome
from gene.models import Gene, GeneSymbol, GeneSymbolImportLog


class Command(BaseCommand):
    '''A custom command to import gene symbol data.'''

    help = 'Imports the data from the named file into the database.'
    args = '<path to CSV-like file>'
  

    def _build_translation_table_from_file(self, translation_file):
        '''Builds a translation table from translation file'''

        master_translation_table = []
        translation_reader = csv.reader(open(translation_file, 'r'), delimiter='\t')
        print '  %s' % translation_file
        for line in translation_reader:
            # Skip empty lines.
            if not line: continue

            # Skip comment/header lines.
            if line[0].startswith('#'): continue

            ## Format: FlyBase FBgn-GLEANR ID Correspondence Table
            #data_fields = ['gene_symbol', 'dpse_flybase_id']
            #data = dict(zip(data_fields, line))
            master_translation_table.append(line)
        return master_translation_table


    def _save_translations_to_db(self, master_translation_table, import_log):
        '''Save all translations to the database, including associations.'''

        count = 0
        skipped = 0
        for translation_rec in master_translation_table:
            count += 1

            # A simple progress indicator, since processing can take a while.
            # Show progress after every thousand lines of gene symbols saved.
            if (count % 100) == 1:
                sys.stdout.write('.')
                sys.stdout.flush()

            if count > 10:
               break

            symbol = translation_rec[0]
            dpse_fbgn_id = translation_rec[1]

            # Ensure reference dpse_fbgn_id already exists. If not, skip this record
            try:
                dpse_fbgn_sym = GeneSymbol.objects.get(symbol=dpse_fbgn_id)
            except:
                skipped+= 1
                continue

            #  Ensure new symbol does not already exist. If it already exists, skip this record
            new_sym = None
            try:
                new_sym = GeneSymbol.objects.get(symbol=symbol)
            except:
                pass

            if new_sym is not None:
                skipped += 1
                continue


            symbol_translations = dpse_fbgn_sym.translations.all()

            # First, construct the new GeneSymbol object
            gene_symbol = GeneSymbol()
            gene_symbol.symbol = symbol
            gene_symbol.save()
            import_log.symbol_count += 1

            gene_symbol.translations.add(dpse_fbgn_sym)
            for s in symbol_translations:
                gene_symbol.translations.add(s)
                import_log.translation_count += 1
            gene_symbol.save()

            dpse_fbgn_sym.translations.add(gene_symbol)
            for s in symbol_translations:
                s.translations.add(gene_symbol)
                import_log.translation_count += 1
                s.save()


    def handle(self, translation_file, **options):
        '''The main entry point for the Django management command.

        '''
    
        time_begin = django.utils.timezone.now()
    
        # Create a new ImportLog object to store metadata about the import.
        file_path = os.path.abspath(translation_file)
        import_log = GeneSymbolImportLog(start=time_begin, 
          file_path=file_path, symbol_count=0, translation_count=0)
        # Start transaction management.
        transaction.commit_unless_managed()
        transaction.enter_transaction_management()
        transaction.managed(True)
    
        try:
            master_translation_table = self._build_translation_table_from_file(translation_file)
            count = self._save_translations_to_db(master_translation_table,
              import_log)
  
            # Finish populating the import meta-data.
            import_log.end = django.utils.timezone.now()
            import_log.calculate_run_time()
      
            # Only save the import metadata if we actually did anything.
            if import_log.symbol_count > 0:    
                import_log.save()
    
        except:
            transaction.rollback()
            transaction.leave_transaction_management()
            raise
    
        # Finalize the transaction and close the db connection.
        transaction.commit()
        transaction.leave_transaction_management()
        connection.close()
    
        # All lines of gene symbol data have been processed, so we can print a
        # short summary of what we did.
        td = import_log.end - import_log.start
        print '\nProcessing complete in %s days, %s.%s seconds.' % (td.days, 
          td.seconds, td.microseconds)
        print '  Gene symbols constructed: %s' % import_log.symbol_count
        print '  Gene symbols translations constructed: %s' % \
          import_log.translation_count
