'''A custom Django administrative command to process "batch gene" requests.

NOTE: Currently, this is designed to be run by cron periodically.  We may have
to implement locking or some sort of collision avoidance mechanism.

NOTE: This will scale horribly, and generally be inefficient.  The current 
usage expectations predict that it shouldn't matter.  If the usage 
expectations change dramatically, this may have to be altered to use a more 
distributed, efficient and sane method of batch processing.

'''

import csv
import datetime
import os
import re
import shutil
import sys
import tempfile
import zipfile

import django.utils.timezone
from django.conf import settings
from django.core.mail import send_mail, mail_managers, EmailMessage
from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.template.loader import render_to_string

from gene.models import Gene, GeneSymbol, GeneBatchProcess
from common.models import Species



class Command(BaseCommand):
    '''A custom command to process "batch gene" requests.
  
    The results of a particular request are stored in a web-accessible 
    directory for delivery.  An e-mail is sent to the user telling them that 
    their results are ready to be retrieved.
  
    '''
  
    help = 'Process any outstanding "batch gene" requests.'
  
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
        for line in file_data:
            f.write('%s\r\n' % line)
        f.close()

    def _write_request(self, request, request_filename='request.txt'):
        '''Write a file with data about the original "batch gene" request.'''
        self._write_file(request_filename, 
          (g_s.strip() for g_s in request.original_request.split('\n')))

    def _write_report(self, report_text, report_filename='report.txt'):
      '''Write a report file with data about the processing of the request.'''
      self._write_file(report_filename, report_text)
  
    def _generate_report_text(self, report_data):
        '''Generate the text of the processing report for the request.'''
        
        report_output = []
        report_output.append('Batch Gene Request Summary: %s tried, %s '
          'succeeded, %s failed' % (report_data['total'], 
            report_data['success'], report_data['failure']))
        report_output.append('')
        if len(report_data['failures']):
            report_output.append('Failures:')
            for f in report_data['failures']:
                report_output.append(f)
            report_output.append('')
        return report_output
  
    def _generate_report_data(self, status_data):
        '''Generate the data used for building the processing report.'''
    
        report = {'total': 0, 'success': 0, 'failure': 0, 'failures': []}
    
        for k in status_data:
          report['total'] += 1
          if status_data[k]['success']:
              report['success'] += 1
          else:
              report['failure'] += 1
              report['failures'].append('%s - %s' % (
                k, status_data[k]['message']))
        
        return report

    def _process_batch_request(self, request):
        '''Process a "batch gene" request and prepare the results.'''
    
        request_status = {'partial': False}
        try:
            # Set up our work area.
            working_directory, results_directory = self._setup_work_area()

            # Indicate that the request is currently being processed.
            request.start()
  
            # Used to track gene processing status.
            gene_status = dict()
  
            # Get the species to process.
            gene_species = request.original_species.split(',')
            gene_species = [Species.objects.get(id=pk) for pk in gene_species]

            show_aligned = request.show_aligned

            # Get the list (actually a generator) of gene symbols to process.
            gene_symbols = (g_s.strip() for g_s in \
              request.original_request.split('\n'))
  
            os.chdir(results_directory)
            # Process each gene.
            for gene_symbol in gene_symbols:
                if not gene_symbol: continue
                gene_status[gene_symbol] = {'success': False, 'message': None}
                try:
                    fasta_output = []
                    for h, b in Gene.multi_gene_fasta(gene_symbol, 
                      gene_species,show_aligned=show_aligned):
                        fasta_output.append(h)
                        fasta_output.append('\r\n'.join(b))
                        
                    # Save the output to a file with the same name as the 
                    # gene_symbol with a "results" postfix.
                    self._write_file('%s-results.txt' % gene_symbol, 
                      fasta_output)
                    gene_status[gene_symbol]['success'] = True
                except GeneSymbol.DoesNotExist:
                    request_status['partial'] = True
                    gene_status[gene_symbol]['message'] = \
                      'Gene symbol "%s" does not exist in Pseudobase.' % \
                        gene_symbol

            # Output a "report.txt" with information about the processing.
            report_data = self._generate_report_data(gene_status)
            report_text = self._generate_report_text(report_data)
            self._write_report(report_text)
  
            # Output a "request.txt" with information about the request.
            self._write_request(request)

            os.chdir(working_directory)
            # Zip up the results and associated metadata about the request.
            r_zip = zipfile.ZipFile(settings.PSEUDOBASE_RESULTS_FILENAME, 'w')
            for g_f in os.listdir(results_directory):
                r_zip.write(os.path.join('pseudobase_results', g_f.strip()))
            r_zip.close()

            delivery_path = os.path.join(settings.PSEUDOBASE_DELIVERY_ROOT, 
              request.delivery_tag)

            # Move the zip into a web-accessible holding area for delivery.
            try:
                os.makedirs(delivery_path)
            except:
                # This just means the path already exists, which is OK.
                raise
            shutil.move(settings.PSEUDOBASE_RESULTS_FILENAME, delivery_path)
  
            # Tear down the work area.
            self._teardown_work_area(working_directory)
    
            # If there were partial failures (of individual genes), mail the 
            # admins.
            if request_status['partial']:
                mail_managers('Batch processing (gene) partial failures.',
                  'There were partial failures during the processing of a '
                  'batch request:\n\n%s' % '\n'.join(report_text))
  
            # Email the user with a notice that their package is ready.
            full_delivery_url = request.full_delivery_url(site=settings.ALLOWED_HOSTS[0])
            email = EmailMessage(
              'Pseudobase: Your batch gene results are now available',
              'The results of your batch gene request are now ready to be '
                'picked up.\n\nThey will be available at the following URL '
                'for seven (7) days:\n\n%s\n\nAdditional information about '
                'your request may be found below:\n\n%s\nThank you for using '
                'Pseudobase!\n\n''' % (full_delivery_url, 
                  '\n'.join(report_text)),
              'django@biology.duke.edu',
              [request.submitter_email], 
              [address for name, address in settings.MANAGERS])
            email.send(fail_silently=False)

            # Update the queue information to indicate the request has been 
            # processed.
            request.total_symbols = report_data['total']
            request.failed_symbols = report_data['failure']
            request.final_report = '\n'.join(report_text)
            request.expiration = (
              django.utils.timezone.now() + datetime.timedelta(days=7))
            request.stop()
            request.save()
        except Exception as e:
            request.stop(batch_status='F')
            request.batch_start = None
            request.batch_end = None
            request.save()
            print('Gene batch failed. Request delivery tag: ',request.delivery_tag,'error: ',e)
            raise
           
    def handle(self, **options):
        '''The main entry point for the Django management command.

         Finds all GeneBatchProcess objects that haven't yet been processed
         and prepares the results for delivery.
    
        '''
    
        for pending_request in GeneBatchProcess.objects.filter(
          batch_status='P'):  
            self._process_batch_request(pending_request)
