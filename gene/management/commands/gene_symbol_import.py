'''A custom Django administrative command for importing gene symbols.

This command imports gene symbols from a series of files acquired from the
FlyBase project.  This is done in order to build a map which can be used to
look up genes based on their various identifiers.

At present, the supported identifiers are:
  Gene name (e.g. atl)
  GA ID (e.g. GA26895)
  CG ID (e.g. CG10064)
  GLEANR ID (e.g. GLEANR_4729)
  FlyBase ID (e.g. FBgn0248267)

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
  
    def _set_if_unset(self, table, identifier, key, value):
        '''Set key/value for a particular identifier in a mapping table.
        
        If the specificed identifier doesn't exist, an entry is created.
        
        Return whether the key/value was set.
        
        '''
        
        was_set = False
        if identifier in table:
            if key not in table[identifier]:
              table[identifier][key] = value
              was_set = True
        else:
            table[identifier] = dict()
            table[identifier][key] = value
            was_set = True
        return was_set

    def _get_unique_symbols(self, sequence):
        '''Return all gene symbols (without duplicates) in sequence.
        
        NOTE: Ordering of the symbols in sequence is not preserved.
        
        '''
      
        keys = {} 
        for e in sequence: 
            keys[e] = 1 
        return keys.keys()

    def _process_fbgn_gleanr_data(self, master_translation_table, data):
        '''Process FlyBase FBgn-GLEANR ID Correspondence Table data.'''
        
        self._set_if_unset(master_translation_table, data['flybase_id'], 
          'gene_symbol', data['gene_symbol'])
        self._set_if_unset(master_translation_table, data['flybase_id'], 
          'flybase_id', data['flybase_id'])
        self._set_if_unset(master_translation_table, data['flybase_id'], 
          'gleanr_id', data['gleanr_id'])

    def _process_fbgn_annotation_data(self, master_translation_table, data):
        '''Process FlyBase FBGN-Annotation ID Correspondence Table data.'''
        
        self._set_if_unset(master_translation_table, data['flybase_id'],
          'gene_name', data['gene_name'])
        self._set_if_unset(master_translation_table, data['flybase_id'], 
          'flybase_id', data['flybase_id'])
        self._set_if_unset(master_translation_table, data['flybase_id'], 
          'annotation_id', data['annotation_id'])

    def _process_ortholog_data(self, master_translation_table, data):
        '''Process FlyBase melanogaster gene ortholog report data.'''
        
        self._set_if_unset(master_translation_table, 
          data['ortholog_flybase_id'], 'ortholog_gene_symbol', 
          data['gene_symbol'])

    def _build_translation_table_from_files(self, translation_files):
        '''Builds a translation table from all files in translation_files.'''

        master_translation_table = dict()
        for tf in translation_files:
            translation_reader = csv.reader(open(tf, 'r'), delimiter='\t')
            print '  %s' % tf
            for line in translation_reader:
                # Skip empty lines.
                if not line: continue

                # Skip comment/header lines.
                if line[0].startswith('#'): continue

                ## Format: FlyBase FBgn-GLEANR ID Correspondence Table
                if len(line) == 3:
                    data_fields = ['gene_symbol', 'flybase_id', 'gleanr_id']
                    data = dict(zip(data_fields, line))

                    # We only want Dpse (D. pseudoobscura) information.
                    if not data['gene_symbol'].startswith('Dpse'): continue

                    self._process_fbgn_gleanr_data(master_translation_table, 
                      data)
                ## Format: FlyBase FBgn-Annotation ID Correspondence Table
                elif len(line) == 5:
                    data_fields = ['gene_name', 'flybase_id', 
                      'sec_flybase_ids', 'annotation_id', 'sec_annotation_id']
                    data = dict(zip(data_fields, line))

                    # We only want Dpse (D. pseudoobscura) information.
                    if not data['gene_name'].startswith('Dpse'): continue

                    self._process_fbgn_annotation_data(
                      master_translation_table, data)
                ## Format: FlyBase melanogaster gene ortholog report
                elif len(line) == 10:
                    data_fields = ['flybase_id','gene_symbol', 'arm', 
                      'location', 'strand', 'ortholog_flybase_id', 
                      'orholog_gene_symbol', 'ortholog_arm', 
                      'ortholog_location', 'ortholog_strand']
                    data = dict(zip(data_fields, line))

                    # Only add ortholog data for genes we want.
                    if data['ortholog_flybase_id'] not \
                      in master_translation_table: 
                        continue

                    self._process_ortholog_data(master_translation_table, 
                      data)
        return master_translation_table

    def _normalize_translation_table(self, master_translation_table):
        '''Clean and normalize all the gene datain the translation table.'''
        
        annotation_search = re.compile(r'^Dpse\\(.+)$').search
        for k in master_translation_table:
            t = master_translation_table[k]
      
            # If there is a symbol or name with a "Dpse\GA" prefix, strip the 
            # prefix and only use the GA portion as an annotation_id.
            if 'gene_symbol' in t and annotation_search(t['gene_symbol']):
                t['annotation_id'] = annotation_search(
                  t['gene_symbol']).group(1)
                del t['gene_symbol']
            if 'gene_name' in t and annotation_search(t['gene_name']):
                t['annotation_id'] = annotation_search(
                  t['gene_name']).group(1)
                del t['gene_name']

    def _save_translations_to_db(self, master_translation_table, import_log):
        '''Save all translations to the database, including associations.'''

        count = 0
        for k in master_translation_table:
            count += 1

            # A simple progress indicator, since processing can take a while.
            # Show progress after every thousand lines of gene symbols saved.
            if (count % 1000) == 1:
                sys.stdout.write('.')
                sys.stdout.flush()

            t = master_translation_table[k]
            symbols = []
            # First, constrct all the GeneSymbol objects.
            for s in self._get_unique_symbols(t.values()):
                gene_symbol = GeneSymbol()
                gene_symbol.symbol = s
                gene_symbol.save()
                symbols.append(gene_symbol)
                import_log.symbol_count += 1

            # Next, link all the GeneSymbol objects to each other.
            for s in symbols:
                for s2 in symbols:
                    if s is s2:
                        continue
                    s.translations.add(s2)
                    import_log.translation_count += 1
                s.save()

    def handle(self, *translation_files, **options):
        '''The main entry point for the Django management command.

        Iterates through all specified files and builds a translation map
        such that every symbol is associated with every equivalent symbol.
        
        NOTE: This can take a while to run, as there are quite a few mappings
        that need to be calculated.
    
        '''
    
        time_begin = django.utils.timezone.now()
    
        # Create a new ImportLog object to store metadata about the import.
        file_paths = ','.join(
          [os.path.abspath(tf) for tf in translation_files])
        import_log = GeneSymbolImportLog(start=time_begin, 
          file_path=file_paths, symbol_count=0, translation_count=0)
    
        # Build the table and normalize all the data.
        print 'Loading gene symbol information from files:'
        master_translation_table = self._build_translation_table_from_files(
          translation_files)
        self._normalize_translation_table(master_translation_table)
        
        # Start transaction management.
        transaction.commit_unless_managed()
        transaction.enter_transaction_management()
        transaction.managed(True)
    
        try:
            # Truncate the existing gene symbol translation table.
            GeneSymbol.objects.all().delete()
      
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
