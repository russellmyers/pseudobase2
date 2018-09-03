'''A custom Django administrative command for importing chromosome data.

This command is intended to be used through Django's standard "management"
command interface, e.g.:

  # ./manage.py chromosome_import <file_to_import>
  
<file_to_import> should be a standard CSV-like chromosome file as constructed
by the Noor lab.

'''

import array
import csv
import os
import re
import struct
import sys

import django.utils.timezone
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection, transaction

from common.models import Strain, Chromosome
from chromosome.models import ChromosomeBase, ChromosomeImportLog


class Command(BaseCommand):
    '''A custom command to import chromosome data from a CSV-like file.'''

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
          'AFC12':     'American Fork Canyon, UT 12',
          'FLG14':     'Flagstaff, AZ 14',
          'FLG16':     'Flagstaff, AZ 16',
          'FLG18':     'Flagstaff, AZ 18',
          'MATHER32':  'Mather, CA 32',
          'MATHERTL':  'Mather, CA TL',
          'MV2-25':    'Mesa Verde, CO 2-25 reference line',
          'MSH9':      'Mount St. Helena, CA 9',
          'MSH24':     'Mount St. Helena, CA 24',
          'PP1134':    'San Antonio, NM, Pikes Peak 1134',
          'BDAPP1134': 'San Antonio, NM, Pikes Peak 1134',
          'PP1137':    'San Antonio, NM, Pikes Peak 1137',
          'BDAPP1137': 'San Antonio, NM, Pikes Peak 1137',
          'BOGNUZ':    'El Recreo white mutant line',
          'BOGERW':    'El Recreo white mutant line',
          'ERW':       'El Recreo white mutant line',
          'BOGTORO':   'Torobarroso',
          'TORO':      'Torobarroso',
          'MSH1993':   'Mount St. Helena, CA 1993',
          'MSH39':     'Mount St. Helena, CA 39',
          'SCI_SR':    'Santa Cruz Island',
          'SCI':       'Santa Cruz Island',
          'MSH22':     'Mount St. Helena, CA 22',
          'SP138':     'SP138',
          'MAO':       'MAO',
          'ARIZ':      'Lowei',
        }
    
        if strain.upper() in STRAIN_TRANSLATION:
            lookup_strain = STRAIN_TRANSLATION[strain.upper()]
    
        try:
            s = Strain.objects.get(name=lookup_strain)
            return (s, False)
        except Strain.DoesNotExist:
            raise
  
    def _lookup_chromosome(self, chromosome):
        '''Load a Chromosome object for association by its name.'''
        return (Chromosome.objects.get(name=chromosome), False)
  
    def _coverage_index(self, n):
        '''Pack n into a byte for use in the coverage index.'''
        return struct.pack('B', n)
  
    def _index(self, n):
        '''Pack n into an integer for use in the base index.'''
        return struct.pack('I', n)
  
    def _reference_format(self, line):
        '''Parse a line in "reference" format and return a list of the data.
      
        The "reference" format is 4 tab-delimited fields, each field containing
        a single value.
      
        NOTE: The coverage value here defaults to 1, as the reference data has
        no coverage information.
      
        '''
        
        return [line[0], line[1], int(line[2]), 1, line[3].upper()]

    def _standard_format(self, line):
        '''Parse a line in "standard" format and return a list of the data.
      
        The "standard" format is 4 tab-delimited fields.  The third field
        contains three space-delimited values.  The first column is empty.
      
        '''

        replace_whitespace = re.compile(r'\s').sub
        base_info = line[3].split(' ', 2)
        return [str(line[1]), str(line[2]), int(base_info[0]), 
          base_info[1].upper(), replace_whitespace('', base_info[2]).upper()]
  
    def _determine_format(self, line):
        '''Determine format and return a reference to the parsing method.'''
    
        if len(line) == 4:
            if line[0]:
                # Reference data format
                return self._reference_format
            else:
                # Standard data format
                return self._standard_format
        else:
            # Invalid data format
            return None
  
    def handle(self, chromosome_data, **options):
        '''The main entry point for the Django management command.
        
        Iterates through the lines in the specified file.  Each line is
        processed by handling the position, coverage and base information.
        
        Binary data files and indexes (by position) are created.  Metadata is
        stored in the database upon successful creation.
        
        WARNING: Chromosome files can be quite large (30M+ records), so this
        script can take a while to complete.  Don't panic.
        
        '''
    
        data_fields = ['chromosome_name', 'strain_name', 'position', 
          'coverage', 'base']
        char_search = re.compile(r'[^ACTGKYSRWMND]').search
        replace_whitespace = re.compile(r'\s').sub
        replace_no_data = re.compile (r'D').sub

        # Create a new ImportLog object to store metadata about the import.
        import_log = ChromosomeImportLog(start=django.utils.timezone.now(),
          file_path=os.path.abspath(chromosome_data), base_count=0, 
          clip_count=0)

        # Start transaction management.
        transaction.commit_unless_managed()
        transaction.enter_transaction_management()
        transaction.managed(True)
    
        # Make a new ChromosomeBase.
        cb = ChromosomeBase()
        cb.file_tag = ChromosomeBase.generate_file_tag()
        cb.start_position = cb.end_position = 0
    
        # Open our data files.
        data_file = open(cb.data_file_path, 'w')
        index_file = open(cb.index_file_path, 'w')
        coverage_file = open(cb.coverage_file_path, 'w')
    
        try:
            print "Constructing ChromosomeBase object from file:\n%s" % \
              chromosome_data
            print "  ",

            # Open the file.
            cb_file = open(chromosome_data)
            chromosome_reader = csv.reader(cb_file, delimiter='\t')
    
            # Read the first line of the file to determine file format.
            example_line = chromosome_reader.next()
            format_parser = self._determine_format(example_line)
            if not format_parser:
                # Unknown data format
                # If the file isn't in the reference or standard data format,
                # we can't do anything with it.
                raise 'Unknown data format!'
            else:
                # Get the data we only want to think about once.
                data = dict(zip(data_fields, format_parser(example_line)))
      
                cb.start_position = data['position']
                cb.strain = self._lookup_strain(data['strain_name'])[0]
                cb.chromosome = self._lookup_chromosome(
                  data['chromosome_name'])[0]
      
                # Reset the file for actual parsing.
                cb_file.seek(0)
                chromosome_reader = csv.reader(cb_file, delimiter='\t')
    
            # Save ChromosomeBase.
            cb.save()
        
            max_position = bases_total = 0
      
            # Now process all the lines in the file.
            for n, line in enumerate(chromosome_reader):
                # Skip empty lines.
                if not line: continue
      
                # A simple progress indicator, since processing can take a 
                # while. Shows progress after every million records processed.
                if not n % (1000 * 1000):
                    sys.stdout.write('.')
                    sys.stdout.flush()
        
                data = dict(zip(data_fields, format_parser(line)))
      
                ## Custom processing to handle data cleanup.
      
                # Change "N" characters in the coverage column to 0.
                # Additionally change the value to be an integer instead of a 
                # string.
                if data['coverage'] == 'N':
                    data['coverage'] = 0

                # Coverages that are above 255 should be clipped to 255, so
                # that we don't need to store 2 bytes of data per coverage.
                data['coverage'] = int(data['coverage'])
                if data['coverage'] > 255:
                    import_log.clip_count += 1
                    data['coverage'] = 255
      
                # Check that the base string contains no invalid characters.
                if char_search(data['base']):
                    print \
                      'Invalid character detected in base - line %s: %s' % \
                        (n, data['base'])
                    break
                else:
                    # Change "D" characters in the base column to "-".
                    data['base'] = replace_no_data(r'-', data['base'])
                    pass
      
                max_position = int(data['position'])
      
                ## Append the base and coverage data to the appropriate files.
        
                # Base data.
                base_string = ''.join(data['base'])
                base_bytes = len(base_string)
                data_file.write(base_string)
      
                # Base data index.
                index_file.write(self._index(bases_total))
                bases_total += base_bytes
        
                # Coverage data.
                coverage_file.write(self._coverage_index(data['coverage']))      
        
            # Base and coverage sequences should now be fully constructed, so 
            # we can save the object.
            cb.end_position = max_position
            cb.save()
              
            # Finish populating the import metadata.
            import_log.base_count = cb.total_bases
            import_log.end = django.utils.timezone.now()
            import_log.calculate_run_time()
      
            # Only save the import metadata if we actually did anything.
            if import_log.base_count > 0:    
                import_log.save()
        
        except:
            data_file.close()
            index_file.close()
            coverage_file.close()
            os.remove(cb.data_file_path)
            os.remove(cb.index_file_path)
            os.remove(cb.coverage_file_path)

            transaction.rollback()
            transaction.leave_transaction_management()

            raise

        data_file.close()
        index_file.close()
        coverage_file.close()
    
        # Finalize the transaction and close the db connection.
        transaction.commit()
        transaction.leave_transaction_management()
        connection.close()
    
        # All lines of chromosome data have been processed, so we can print a 
        # short summary of what we did.
        td = import_log.end - import_log.start
        print '\nProcessing complete in %s days, %s.%s seconds.' % \
          (td.days, td.seconds, td.microseconds)
        print '  ChromosomeBase objects constructed: 1'
        print '  Total bases: %s' % import_log.base_count
        print '  Total coverages clipped: %s' % import_log.clip_count
