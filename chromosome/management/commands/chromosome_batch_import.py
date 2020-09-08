'''A custom Django administrative command to process "batch gene" requests.

NOTE: Currently, this is designed to be run by cron periodically.  We may have
to implement locking or some sort of collision avoidance mechanism.

NOTE: This will scale horribly, and generally be inefficient.  The current 
usage expectations predict that it shouldn't matter.  If the usage 
expectations change dramatically, this may have to be altered to use a more 
distributed, efficient and sane method of batch processing.

'''


from django.core.management.base import BaseCommand
from chromosome.models import ChromosomeBatchImportProcess, ChromosomeImporter
from optparse import make_option
import logging
log = logging.getLogger(__name__)


class Command(BaseCommand):
    '''A custom command to process "chromososome batch import" requests.
    '''

    option_list = BaseCommand.option_list + (
        make_option('-f', '--flybasereleaseversion',
                    dest='flybase_release',
                    default='pse1',
                    help='Flybase release version aligned against (eg r3.04)'),
    )

    def _process_batch_import_request(self, request, options):
        '''Process a "chromosome batch import" request '''
    
        #request_status = {'partial': False}
        try:
            # Set up our work area.
            #working_directory, results_directory = self._setup_work_area()

            # Indicate that the request is currently being processed.
            request.start() # In Progress
            
            request.save() #save immediately,so no other process will start
            
            batch_file_list = [batch_file.strip() for batch_file in request.original_request.split('\n')]
            
            #for pending_import_file in request.chromosomebatchimportlog_set.filter(status = 'P'):
            for batch_file in batch_file_list:
                try:
                    chr_importer = ChromosomeImporter(batch_file,flybase_release=options['flybase_release'])
                    chr_importer.import_data(request)
                    chr_importer.print_summary()
                    
                except Exception as e:
                    print ('chromosome importer failed: ',batch_file, ' Reason: ',e)
                    pass
            
  
            request.stop(batch_status='C')
            request.save()  
 
        except Exception:
            request.stop(batch_status='F')
            request.save()
            raise
           
    def handle(self, **options):
        '''The main entry point for the Django management command.

         1) Check if any Chromosome Batch Import processes are already running
                => If so: exit (one at a time!)
                
         2) Check for any Pending Chromsome Batch Import processes
                => If found: execute one    
    
        '''
    
        running_batches = ChromosomeBatchImportProcess.objects.running_batches()
        if (len(running_batches) > 0):
            log.info('Batch already running. Exiting')
            return
            
        
        pending_batches = ChromosomeBatchImportProcess.objects.pending_batches()
        
        if (len(pending_batches) > 0):
            self._process_batch_import_request(pending_batches[0],options)
        else:
           print ('No pending batches to process')
