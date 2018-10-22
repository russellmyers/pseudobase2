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
import django.utils.timezone


class Command(BaseCommand):
    '''A custom command to process "chromososome batch import" requests.
    '''
 

    def _process_batch_import_request(self, request):
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

                print ('pending: ',batch_file)
                try:
                    #pending_import_file.status = 'A'
                    #pending_import_file.start = django.utils.timezone.now()
                    #pending_import_file.save()
                    
                    chr_importer = ChromosomeImporter(batch_file)
                    chr_importer.import_data(request)
                    chr_importer.print_summary()
                    
                    #pending_import_file.chromebase = chr_importer.cb
                    #pending_import_file.clip_count = chr_importer.import_log.clip_count
                    #pending_import_file.base_count = chr_importer.cb.total_bases
                    #pending_import_file.status = 'C'
                    #pending_import_file.end = django.utils.timezone.now()
                    #pending_import_file.run_microseconds = pending_import_file.calculate_run_time()

                    #pending_import_file.save()
                    
                except:
                    print ('chromosome importer failed: ',batch_file)
                    #pending_import_file.status = 'F'
                    #pending_import_file.end = django.utils.timezone.now()
                    #pending_import_file.save()
                    pass
            
  
            request.stop(batch_status='C')
            request.save()  
 
        except Exception:
            request.stop(batch_status='F')
            #request.batch_start = None
            #request.batch_end = None
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
            print ('Batch already running. Exiting')
            return
            
        
        pending_batches = ChromosomeBatchImportProcess.objects.pending_batches()
        
        if (len(pending_batches) > 0):
            self._process_batch_import_request(pending_batches[0])
        else:
           print ('No pending batches to process') 
