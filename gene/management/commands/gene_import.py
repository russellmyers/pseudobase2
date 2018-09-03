'''A custom Django administrative command for importing gene data.

This command imports gene data from a CSV-like file provided by the Noor lab.
Each "record" (i.e. an individual sequence of gene data) is created as an
individual object within the database.

The supported format for this command is as follows (tab-delimited):
Field 1: chromsome name, appended with underscore and first base position
  e.g. 2_1772
Field 2: import code
  e.g. dpse_GLEANR_4729
Field 3: strand (this field can be ignored)
Field 4: species code (translate into appropriate full species name)
  e.g. pse
Field 5: strain code (translate into appropriate full strain name)
  e.g. pp134
Field 6: bases (sequence data)
  e.g. ATGCGCCGG...

'''

import csv
import os
import re
import sys

import django.utils.timezone
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection, transaction

from common.models import Strain, Chromosome
from gene.models import Gene, GeneImportLog


class Command(BaseCommand):
    '''A custom command to import gene data from a CSV-like file.'''
    
    help = 'Imports the data from the named file into the database.'
    args = '<path to CSV-like file>'
  
    def _lookup_strain(self, strain):
        '''Load a Strain object for association by its "short name".
    
        First, translate the "short name" of the strain into the appropriate
        "full name".  Then, look up the "full name" to get the related object
        which we can then use for associations.
        
        NOTE: We could (should) do this programmatically if we added a table
        that mapped common strain notation to the appropriate Strain object.
        It isn't necessary during the time crunch (a.k.a. now), but it should
        probably be done if the translation table ends up changing often.
    
        '''

        STRAIN_TRANSLATION = {
          'AFC12':    'American Fork Canyon, UT 12',
          'FLAG14':   'Flagstaff, AZ 14',
          'FLAG16':   'Flagstaff, AZ 16',
          'FLAG18':   'Flagstaff, AZ 18',
          'MATHER32': 'Mather, CA 32',
          'MATHERTL': 'Mather, CA TL',
          'MV2_25':   'Mesa Verde, CO 2-25 reference line',
          'MSH9':     'Mount St. Helena, CA 9',
          'MSH24':    'Mount St. Helena, CA 24',
          'PP1134':   'San Antonio, NM, Pikes Peak 1134',
          'PP1137':   'San Antonio, NM, Pikes Peak 1137',
          'ERW':      'El Recreo white mutant line',
          'TORO':     'Torobarroso',
          'MSH1993':  'Mount St. Helena, CA 1993',
          'MSH39':    'Mount St. Helena, CA 39',
          'SCISR':    'Santa Cruz Island',
          'MSH22':    'Mount St. Helena, CA 22',
          'MSH3':     'Mount St. Helena, CA 3',
          'SP138':    'SP138',
          'MAO':      'MAO',
          'ARIZ':     'Lowei',
        }
    
        if strain.upper() in STRAIN_TRANSLATION:
            lookup_strain = STRAIN_TRANSLATION[strain.upper()]
        s = Strain.objects.get(name=lookup_strain)
        return (s, False)
  
    def _lookup_chromosome(self, chromosome):
        '''Load a Chromosome object for association by its name.'''
        return (Chromosome.objects.get(name=chromosome), False)
  
    def _save_gene(self, chromosome_name, strain_name, start_position, 
      import_code, bases):
        '''Create and save a new gene constructed from the passed data.
        
        Type coercion can happen here, but any other data munging should 
        occur before this method is called.
    
        '''
      
        g = Gene()
        g.strain = self._lookup_strain(strain_name)[0]      
        g.chromosome = self._lookup_chromosome(chromosome_name)[0]
        g.start_position = int(start_position)
        g.end_position = int(start_position + (len(bases) - 1))
        g.import_code = import_code 
        g.bases = bases
        g.save()

    def _rollback_db(self):
        '''Roll back the database transaction (use in error conditions.)'''
        
        transaction.rollback()
        transaction.leave_transaction_management()

    def handle(self, gene_data, **options):
        '''The main entry point for the Django management command.
    
        Iterates through the lines in the specified file.  Each line contains
        sequence data for a particular gene.  Once massaged into appropriate
        formats, a new Gene object is created and saved to the database.
    
        WARNING: This script can take up a lot of resources when processing a
        file with a lot of gene sequences.  Steps have been taken to minimize 
        the impact, but there is only so much that can be done.  Plan to have 
        a large (10K+ records) file take a few minutes to process.
    
        '''
    
        time_begin = django.utils.timezone.now()
    
        print 'Constructing Gene objects from file:\n%s' % gene_data
        print '  ',
    
        gene_reader = csv.reader(open(gene_data, 'r'), delimiter='\t')
    
        # Start transaction management.
        transaction.commit_unless_managed()
        transaction.enter_transaction_management()
        transaction.managed(True)
        
        # Create a new ImportLog object to store metadata about the import.
        import_log = GeneImportLog(start=time_begin, 
          file_path=os.path.abspath(gene_data), gene_count=0)
    
        split_search = re.compile(r'^(.+)_(\d+)$').search
        char_search = re.compile(r'[^ACTGN\_]').search
        replace_no_data = re.compile(r'[_]').sub
        for line in gene_reader:
            # Skip empty lines.
            if not line: continue
      
            # Skip the header line.
            if line[0] == 'base': continue
      
            import_log.gene_count += 1
            # A simple progress indicator, since processing can take a while.
            # Show progress after every thousand genes processed.
            if (import_log.gene_count % (1000)) == 1:
                sys.stdout.write('.')
                sys.stdout.flush()
      
            # Process chromosome and start_position.
            m = split_search(line[0])
            chromosome_name = m.group(1)
            start_position = int(m.group(2))

            # Process import_code.
            import_code = line[1]
      
            # Process strain.
            strain_name = line[4].upper().replace(r'BDA', '')
      
            # Process bases.
            # Check that the base string contains no invalid characters.
            bases = line[5]
      
            # Check that the base string contains no invalid characters.
            if char_search(bases):
                print "Invalid character detected in base for line: '%s'" % \
                  bases
                break
            else:
                # Change "D" characters in the base column to "-".
                bases = replace_no_data(r'-', bases)
      
            try:
                self._save_gene(chromosome_name, strain_name, start_position, 
                  import_code, bases)
            except:
                self._rollback_db()
                raise

        # Finish populating the import meta-data.
        import_log.end = django.utils.timezone.now()
        import_log.calculate_run_time()

        # Only save the import metadata if we actually did anything.
        if import_log.gene_count > 0:    
            try:
                import_log.save()
            except:
                self._rollback_db()
                raise
    
        # Finalize the transaction and close the db connection.
        transaction.commit()
        transaction.leave_transaction_management()
        connection.close()
    
        # All lines of gene data have been processed, so we can print a short
        # summary of what we did.
        td = import_log.end - import_log.start
        print '\nProcessing complete in %s days, %s.%s seconds.' % (td.days,
          td.seconds, td.microseconds)
        print '  Gene objects constructed: %s' % import_log.gene_count
