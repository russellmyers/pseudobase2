'''A custom Django administrative command for exporting chromosome data.

This command is intended to be used through Django's standard "management"
command interface, e.g.:

  # ./manage.py chromosome_feature_export <strain_id_to_export>
  
<strain_id_to_export> should be the strain_id of the relevant strain

This export script was originally created by special request for Mohamed Noor.

'''

import os
import shutil
import subprocess
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
    '''A custom command to export chromosome data about a specific strain.'''

    help = 'Exports chromosome data for a specific strain.'
    args = '<strain_id> <strain_tag>'
  
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
  
    def handle(self, strain_id, strain_tag, **options):
        '''The main entry point for the Django management command.
        
        Iterates through each chromosome for the specified strain, outputting
        a FASTA-formatted file with the relevant data.  When all output is
        is complete, the directory is zipped and then removed.
                
        '''

        # Store some metadata about the export for display later.
        export_start = django.utils.timezone.now()
        export_files_count = 0

        print "Exporting chromosome data for strain with ID: %s" % \
          strain_id
        print "  ",

        try:
            # Set up our work area.
            cdate = datetime.now()
            results_dirname = "pseudobase_results-%s%02d%02d.%02d%02d%02d" % (
              cdate.year, cdate.month, cdate.day, cdate.hour, cdate.minute,
              cdate.second)
            working_directory, results_directory = self._setup_work_area(
              results_dirname)
        
            for c in ChromosomeBase.objects.filter(strain__id=strain_id):
        
                export_filename = os.path.join("%s" % results_dirname, 
                  "%s_%s.txt" % (strain_tag, c.chromosome.name))
                export_file = open(export_filename, 'a')
                
                export_file.write('%s\n' % \
                  c.fasta_header(c.start_position, c.end_position))
                export_file.close()
                export_file = open(export_filename, 'a')
                subprocess.call(['/usr/bin/fold', '-c75', c.data_file_path], 
                  stdout=export_file)
                export_file.close()

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
        print '  Total strain files exported: %s' % export_files_count
