'''A custom Django administrative command for exporting chromosome data.

This command is intended to be used through Django's standard "management"
command interface, e.g.:

  # ./manage.py chromosome_feature_export <file_to_import>
  
<file_to_import> should be a standard CSV file with 4 fields:
 - feature id
 - chromosome number
 - start position
 - end position

This export script was originally created by special request for Kevin Nyberg 
(kevingnyberg@gmail.com), a graduate student in Carlos Machado's lab at the 
University of Maryland.

'''

import csv
import os
import shutil
import sys
import tempfile
import zipfile
from datetime import datetime

import django.utils.timezone
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import connection, transaction
from django.template.loader import render_to_string

from chromosome.models import ChromosomeBase
from common.models import Chromosome


class Command(BaseCommand):
    '''A custom command to import chromosome data from a CSV-like file.'''

    help = 'Exports chromosome data for the features listed in the input file.'
    args = '<path to CSV-like file>'
  
    def _setup_work_area(self, results_directory='pseudobase_results'):
        '''Set up temporary directories for storing any intermediate files.'''

        working_directory = tempfile.mkdtemp()
        results_directory = os.path.join(working_directory, results_directory)
        os.mkdir(results_directory)
        os.chdir(working_directory)
        return (working_directory,results_directory)

    def _teardown_work_area(self, working_directory):
        '''Tear down temporary directories created for temporary storage.'''
        shutil.rmtree(working_directory)
        
    def _write_file(self, file_name, file_data):
        '''Write a line to file file_name per line of file_data.'''
        
        f = open(file_name, 'w')
        f.write('%s\n' % file_data)
        f.close()
  
    def handle(self, chromosome_data, **options):
        '''The main entry point for the Django management command.
        
        Iterates through the lines in the specified file.  Each line is
        processed by handling the feature id, chromosome, start position and
        end position.  Multi-FASTA output for each feature is created in a
        temporary directory.  When all output is complete, the directory is
        zipped and then removed.
                
        '''

        # Store some metadata about the export for display later.
        export_start = django.utils.timezone.now()
        export_files_count = 0

        data_fields = ['feature_id', 'chromosome_name', 'start_position', 
          'end_position']

        input_file = open(chromosome_data)
        chromosome_reader = csv.reader(input_file)
        
        print "Exporting feature chromosome from input file:\n%s" % \
          chromosome_data
        print "  ",

        try:
            # Set up our work area.
            cdate = datetime.now()
            results_dirname = "pseudobase_results-%s%02d%02d.%02d%02d%02d" % (
              cdate.year, cdate.month, cdate.day, cdate.hour, cdate.minute,
              cdate.second)
            working_directory, results_directory = self._setup_work_area(
              results_dirname)
        
            for n, line in enumerate(chromosome_reader):
                # Skip empty lines.
                if not line: continue
            
                data = dict(zip(data_fields, line))

                # A simple progress indicator, since processing can take a 
                # while. Shows progress after every thousand records processed.
                if not n % (1000):
                    sys.stdout.write('.')
                    sys.stdout.flush()

                custom_data = dict()
                custom_data['fasta_objects'] = ChromosomeBase.multi_strain_fasta(
                  Chromosome.objects.get(name=data['chromosome_name']),
                  (1,2,3,4,5),
                  int(data['start_position']),
                  int(data['end_position']))
                multi_fasta = render_to_string('chromosome_feature_export.txt', 
                  custom_data)

                self._write_file(os.path.join("%s" % results_dirname, "%s.txt" % 
                  data['feature_id']), multi_fasta)

                export_files_count += 1        

            # Zip up the results and associated metadata about the request.
            r_zip = zipfile.ZipFile("%s.zip" % results_dirname, 'w')
            for g_f in os.listdir(results_directory):
                r_zip.write(os.path.join('%s' % results_dirname, g_f.strip()))
            r_zip.close()

            # Move the zip into a web-accessible holding area for delivery.
            shutil.move("%s.zip" % results_dirname, settings.PSEUDOBASE_DELIVERY_ROOT)

        except:
          # Tear down the work area.
          self._teardown_work_area(working_directory)
        
          raise 
        
        # Tear down the work area.
        self._teardown_work_area(working_directory)
  
        export_end = django.utils.timezone.now()
    
        # All lines of chromosome data have been processed, so we can print a 
        # short summary of what we did.
        td = export_end - export_start
        print '\nProcessing complete in %s days, %s.%s seconds.' % \
          (td.days, td.seconds, td.microseconds)
        print '  Total features exported: %s' % export_files_count
