'''A custom Django administrative command for importing chromosome data.

This command is intended to be used through Django's standard "management"
command interface, e.g.:

  # ./manage.py chromosome_import <file_to_import>
  
<file_to_import> should be a standard CSV-like chromosome file as constructed
by the Noor lab.

'''

from django.core.management.base import BaseCommand
from chromosome.models import ChromosomeImporter,ChromosomeBatchImportProcess
from optparse import make_option
from django.db import connection, transaction
import os
import django.utils.timezone



class Command(BaseCommand):
    '''A custom command to import chromosome data from a CSV-like file.'''

    help = 'Imports the data from the named file into the database.'
    args = '<path to CSV-like file>'

    option_list = BaseCommand.option_list + (
        make_option('-f', '--flybasereleaseversion',
                    dest='flybase_release',
                    default='pse1',
                    help='Flybase release version aligned against (eg r3.04)'),
        make_option('-r', '--refchrom',
                    dest='ref_chrom',
                    help='import reference chromosome name'),

    )


    def handle(self, chromosome_data, **options):
        '''The main entry point for the Django management command.
        
        Iterates through the lines in the specified file.  Each line is
        processed by handling the position, coverage and base information.
        
        Binary data files and indexes (by position) are created.  Metadata is
        stored in the database upon successful creation.
        
        WARNING: Chromosome files can be quite large (30M+ records), so this
        script can take a while to complete.  Don't panic.
        
        '''
 
        #Perform this legacy command by creating a batch of one file and  calling the new batch import process

        print('chromosome_data: ',chromosome_data)
        print('Flybase release version: ', options['flybase_release'])
        print('Ref chrom import: ',options['ref_chrom'])


        try:
            bp = ChromosomeBatchImportProcess.create_batch_and_import_file(chromosome_data,flybase_release=options['flybase_release'],ref_chrom=options['ref_chrom'])
            print('bp: ',bp)
        except:
            raise
            


 
            
            

   
