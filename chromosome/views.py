'''Views for the common application.'''

import os

from django.shortcuts import render_to_response,redirect
from django.template import RequestContext
from django.contrib import messages
from django.http import HttpResponse
import django.utils.timezone
from django.db import connection, transaction
from django.conf import settings

import chromosome.forms
from chromosome.models import ChromosomeBase, ChromosomeImporter, ChromosomeBatchImportProcess, ChromosomeBatchImportLog

    
def import_files(request):
    
    
    mypath = settings.PSEUDOBASE_CHROMOSOME_RAW_DATA_PENDING_PREFIX  #'raw_data/chromosome/pending_import/'
    abspath = os.path.abspath(mypath)

    if request.method == 'POST':
        print ('posttt')    
        form = chromosome.forms.ImportForm(request.POST)
        selected_values = request.POST.getlist('import_files')
        
        # Start transaction management.
        transaction.commit_unless_managed()
        transaction.enter_transaction_management()
        transaction.managed(True)
        try:
            if (len(selected_values) == 0):
               raise Exception('No files selected for import')
               
            current_batches = ChromosomeBatchImportProcess.objects.current_batches() #ChromosomeBatchImportProcess.objects.filter(Q(batch_status='P') | Q(batch_status='I'))   
            if (len(current_batches) > 0):
               raise Exception('Batch import already in process. Please wait ')
            
            bp = ChromosomeBatchImportProcess(submitted_at = django.utils.timezone.now(),batch_status = 'P')
            
#            orig_req = ''
#            for i,sel_file in enumerate(selected_values):
#               file_path = os.path.join(abspath,sel_file)
#               orig_req += file_path
#               if i == len(selected_values) - 1:
#                   pass
#               else:
#                   orig_req += '\n'
#            bp.original_request = orig_req   
            bp.set_orig_request_from_filenames(selected_values)
            
            bp.save()
            
           
            # Finalize the transaction and close the db connection.
            transaction.commit()
            transaction.leave_transaction_management()
            connection.close()
            messages.success(request, str(len(selected_values)) + ' files selected for import',extra_tags='html_safe alert alert-success')
            return redirect(import_progress)
        except Exception as e:
            transaction.rollback()
            transaction.leave_transaction_management()

            messages.error(request, 'Batch import process failed: ' + str(e),extra_tags='html_safe alert alert-danger')
            return redirect(import_files)
        
#        if form.is_valid():
#           print ('form is valid')   
#           cd = form.cleaned_data
#           print ('cd: ',cd['import_files'])
#        else:
#           print ('failed validation: ',form.cleaned_data) 
    
    current_batches = ChromosomeBatchImportProcess.objects.current_batches() #ChromosomeBatchImportProcess.objects.filter(Q(batch_status='P') | Q(batch_status='I'))   
    if (len(current_batches) > 0):
       return redirect(import_progress)
    
    custom_data = {}
    custom_data['tab'] = 'Import'
    
    from os import listdir
    from os.path import isfile, join
    custom_data['pending_import_path'] = abspath
    files = [f for f in listdir(mypath) if isfile(join(mypath, f))]
   
    
    files_info = []
    for f in files:
        c_importer = ChromosomeImporter(join(mypath, f))
        file_info = c_importer.get_info(incl_rec_count = False)
        
        if 'file_size' in file_info:
           file_info['file_size_MB'] = "%.2fMB" % file_info['file_size']
           
        files_info.append(file_info)

    num_valid_pending_files = 0        
    for f_info in files_info:
        if (f_info['format'] == 'unknown'):
            pass
        else:
            num_valid_pending_files +=1
    custom_data['num_valid_pending_files'] = num_valid_pending_files       
        
    
    custom_data['pending_files'] = files_info  
    
    #Get recent completed imports
    custom_data['recent_imports'] = ChromosomeBatchImportLog.objects.filter(status='C').order_by('-end')
        
    
    return render_to_response('import.html', custom_data,
      context_instance=RequestContext(request))   
 
def import_progress(request):
    
    mypath = settings.PSEUDOBASE_CHROMOSOME_RAW_DATA_PENDING_PREFIX #'raw_data/chromosome/pending_import/'
    abspath = os.path.abspath(mypath)
    
    progress_texts = {'P':'Pending','A':'Running','C':'Completed','F':'Err - Failed','M':'Err - Duplicate','X':'Err - Exception'}
    
    current_batches = ChromosomeBatchImportProcess.objects.current_batches() #ChromosomeBatchImportProcess.objects.filter(Q(batch_status='P') | Q(batch_status='I'))   
    if (len(current_batches) > 0):
        current_batch = current_batches[0]
        #current_batch_import_file_logs = current_batch.chromosomebatchimportlog_set.all()
        file_progress_dict = {}
        batch_file_list = [batch_file.strip() for batch_file in current_batch.original_request.split('\n')]
    
        #for rb in current_batch_import_file_logs:
        for batch_file in batch_file_list:
            try:
               file_log = ChromosomeBatchImportLog.objects.get(batch=current_batch,file_path = batch_file)
               file_progress_dict[os.path.split(batch_file)[1]] = file_log.status  
            except ChromosomeBatchImportLog.DoesNotExist:
                file_progress_dict[os.path.split(batch_file)[1]] = 'P' 
            except ChromosomeBatchImportLog.MultipleObjectsReturned:
                file_progress_dict[os.path.split(batch_file)[1]] = 'M'
            except:
                file_progress_dict[os.path.split(batch_file)[1]] = 'X'
            
              
    else:
        messages.success(request, 'Import(s) completed!',extra_tags='html_safe alert alert-success')
        return redirect(import_files)
        
    
    custom_data = {}
    custom_data['tab'] = 'Import Progress'
    
    custom_data['pending_import_path'] = abspath

    files_info = []
    
    status = ''
    for fl in batch_file_list:
        f = os.path.split(fl)[1]
        if f in file_progress_dict:
           status = file_progress_dict[f] 
           
        if ((status == 'A') or (status == 'C')):
            # don't attempt to read, already open or alreast removed from pending imports folder
            file_info = {}
            print ('status: ',status)
            print ('prog text: ',progress_texts[status])
            file_info['import_status'] = progress_texts[status]
            file_info['file_name'] = f
            file_info['format'] = '*'
            print('fie info: ',file_info)
        else:    
            c_importer = ChromosomeImporter(fl)   #join(mypath, f))
            file_info = c_importer.get_info(incl_rec_count = False)
            
            if 'file_size' in file_info:
               file_info['file_size_MB'] = "%.2fMB" % file_info['file_size']
        
            if f in file_progress_dict:
               status = file_progress_dict[f] 
               if status in progress_texts: 
                  file_info['import_status'] = progress_texts[status]
               else:
                  file_info['import_status'] = 'Unknown' 
                  
        files_info.append(file_info)
    
    custom_data['pending_files'] = files_info  
    
    #Get recent completed imports
    custom_data['recent_imports'] = ChromosomeBatchImportLog.objects.filter(status='C').order_by('-end')
        
    
    return render_to_response('import_progress.html', custom_data,
      context_instance=RequestContext(request))       
    
def import_file(request,fname=''):
    custom_data = {}
    custom_data['tab'] = 'Import File'
    custom_data['fname'] = fname
    print ('fname: ',fname)
    
    mypath = settings.PSEUDOBASE_CHROMOSOME_RAW_DATA_PENDING_PREFIX #'raw_data/chromosome/pending_import/'
    from os.path import join
    rel_path = join(mypath, fname)
    
    try:
        c_importer = ChromosomeImporter(rel_path)
        file_info = c_importer.get_info(incl_rec_count = True)
        custom_data['file_info'] = file_info

        ChromosomeBatchImportProcess.create_batch_and_import_file(rel_path)
        messages.success(request, 'File imported successfully!',extra_tags='html_safe alert alert-success')
        return redirect(import_files)

    except Exception as e:
        custom_data['file_info'] = {'error':e}
    
    return render_to_response('import_file.html', custom_data,
      context_instance=RequestContext(request))   

def _delete_latest(request):
    custom_data = {}
    custom_data['tab'] = 'Delete File'
    
    try:
        chrBase = ChromosomeBase.objects.all().order_by('-id')[0]
        tag = chrBase.file_tag
            
        print ('Tag: ',tag)
        
        #latestLog = ChromosomeImportLog.objects.all().order_by('-id')[0]
        latestBatchLog = ChromosomeBatchImportLog.objects.all().order_by('-id')[0]
        
        fpath = latestBatchLog.file_path
        print ('latest log: ',fpath)
        
        sourcepath = settings.PSEUDOBASE_CHROMOSOME_RAW_DATA_IMPORTED_PREFIX #'raw_data/chromosome/'
        destpath =  settings.PSEUDOBASE_CHROMOSOME_RAW_DATA_PENDING_PREFIX #'raw_data/chromosome/pending_import/'
        head, tail = os.path.split(fpath) 
  
        print ('moving: ',  os.path.join(sourcepath,tail))
        print (' ..to: ',os.path.join(destpath,tail))
        os.rename(os.path.join(sourcepath,tail), os.path.join(destpath,tail)) 
    except Exception as e:
        print('couldnt get latest chromosomebase or chromosomeimportlog')
        messages.error(request, 'Latest not deleted!' + str(e),extra_tags='html_safe alert alert-danger')
        return redirect(import_files)
    
    if os.path.exists(chrBase.data_file_path):
        os.remove(chrBase.data_file_path)
        print ('removed: ',chrBase.data_file_path)

    if os.path.exists(chrBase.index_file_path):
        os.remove(chrBase.index_file_path)
        print ('removed: ',chrBase.index_file_path)  

    if os.path.exists(chrBase.coverage_file_path): 
        os.remove(chrBase.coverage_file_path)
        print ('removed: ',chrBase.coverage_file_path)  
   

  
    chrBase.delete()
    #latestLog.delete()
    latestBatchLog.delete()
    messages.success(request, 'Latest deleted successfully!',extra_tags='html_safe alert alert-success')
    return redirect(import_files)
 

