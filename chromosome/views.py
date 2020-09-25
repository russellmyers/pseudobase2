'''Views for the common application.'''

import os

from django.shortcuts import render_to_response,redirect
from django.template import RequestContext
from django.contrib import messages
from django.http import HttpResponse
import django.utils.timezone
from django.db import connection, transaction
from django.conf import settings
import json

import logging
log = logging.getLogger(__name__)

import chromosome.forms
from chromosome.models import ChromosomeBase, ChromosomeImporter, ChromosomeBatchImportProcess, ChromosomeBatchImportLog, ChromosomeBatchPreprocess


def preprocess_files_old(request):
    mypath = settings.PSEUDOBASE_CHROMOSOME_RAW_DATA_VCF_PREFIX  # 'raw_data/chromosome/pending_import/'
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

            current_batches = ChromosomeBatchImportProcess.objects.current_batches()  # ChromosomeBatchImportProcess.objects.filter(Q(batch_status='P') | Q(batch_status='I'))
            if (len(current_batches) > 0):
                raise Exception('Batch import already in process. Please wait ')

            bp = ChromosomeBatchImportProcess(submitted_at=django.utils.timezone.now(), batch_status='P')

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
            messages.success(request, str(len(selected_values)) + ' files selected for import',
                             extra_tags='html_safe alert alert-success')
            return redirect(import_progress)
        except Exception as e:
            transaction.rollback()
            transaction.leave_transaction_management()

            messages.error(request, 'Batch import process failed: ' + str(e), extra_tags='html_safe alert alert-danger')
            return redirect(import_files)



    # current_batches = ChromosomeBatchImportProcess.objects.current_batches()  # ChromosomeBatchImportProcess.objects.filter(Q(batch_status='P') | Q(batch_status='I'))
    # if (len(current_batches) > 0):
    #     return redirect(import_progress)

    custom_data = {}
    custom_data['tab'] = 'Preprocess'

    from os import listdir
    from os.path import isfile, join
    custom_data['pending_preprocess_path'] = abspath
    files = [f for f in listdir(mypath) if isfile(join(mypath, f))]
    directories = [d for d in listdir(mypath) if not isfile(join(mypath,d))]

    files_info = []
    for f in files:
        c_importer = ChromosomeImporter(join(mypath, f))
        file_info = c_importer.get_info(incl_rec_count=False)

        if 'file_size' in file_info:
            file_info['file_size_MB'] = "%.2fMB" % file_info['file_size']

        if file_info['format'] == 'unknown':
            pass
        else:
            files_info.append(file_info)

    num_valid_pending_preprocess_files = 0
    for f_info in files_info:
        if (f_info['format'] == 'unknown'):
            pass
        else:
            num_valid_pending_preprocess_files += 1
    custom_data['num_valid_pending_preprocess_files'] = num_valid_pending_preprocess_files

    custom_data['pending_files'] = files_info

    # Get recent completed imports
    custom_data['recent_imports'] = ChromosomeBatchImportLog.objects.filter(status='C').order_by('-end')


    dirs_info = []

    preprocessed_files_info = []
    split_files_info = []
    filtered_files_info = []
    indel_files_info = []

    for d in directories:
        if d[:1] == 'D':
            dir_info = {}
            dir_info['strain'] = d

            strain_dir = join(mypath,d)
            # strain_files = [f for f in listdir(strain_dir) if isfile(join(strain_dir,f))]
            #
            # for f in strain_files:
            #     c_importer = ChromosomeImporter(join(strain_dir, f))
            #     preprocessed_file_info = c_importer.get_info(incl_rec_count=False)
            #
            #     if 'file_size' in preprocessed_file_info:
            #         preprocessed_file_info['file_size_MB'] = "%.2fMB" % preprocessed_file_info['file_size']
            #
            #     preprocessed_file_info['strain'] = d
            #     preprocessed_file_info['type'] = 'Split'
            #     preprocessed_files_info.append(preprocessed_file_info)

            strain_subdirectories = [d_sub for d_sub in listdir(strain_dir) if not isfile(join(strain_dir, d_sub))]
            #dir_info['split'] = len(strain_files)

            for sub_dir in strain_subdirectories:
                strain_subdir = join(strain_dir, sub_dir)
                strain_subdir_files = [f for f in listdir(strain_subdir) if
                                       isfile(join(strain_subdir, f))]

                for f in strain_subdir_files:
                    c_importer = ChromosomeImporter(join(strain_subdir, f))
                    preprocessed_file_info = c_importer.get_info(incl_rec_count=False)

                    if 'file_size' in preprocessed_file_info:
                        preprocessed_file_info['file_size_MB'] = "%.2fMB" % preprocessed_file_info['file_size']

                    preprocessed_file_info['strain'] = d
                    preprocessed_file_info['type'] = sub_dir
                    if sub_dir == 'split':
                       split_files_info.append(preprocessed_file_info)
                    elif sub_dir == 'filtered':
                       filtered_files_info.append(preprocessed_file_info)
                    else:
                        indel_files_info.append(preprocessed_file_info)
                    #preprocessed_files_info.append(preprocessed_file_info)
                # if sub_dir == 'filtered':
                #     strain_filtered_dir = join(strain_dir,sub_dir)
                #     strain_filtered_files = [f for f in listdir(strain_filtered_dir) if isfile(join(strain_filtered_dir, f))]
                #     dir_info['filtered'] = len(strain_filtered_files)
                #
                # elif sub_dir == 'indels':
                #     strain_indels_dir = join(strain_dir, sub_dir)
                #     strain_indels_files = [f for f in listdir(strain_indels_dir) if   isfile(join(strain_indels_dir, f))]
                #     dir_info['indels'] = len(strain_indels_files)
            dirs_info.append(dir_info)

    num_valid_split_files = 0
    for f_info in split_files_info:
        if (f_info['format'] == 'unknown'):
            pass
        else:
            num_valid_split_files += 1

    custom_data['num_valid_split_files'] = num_valid_split_files

    num_valid_filtered_files = 0
    for f_info in filtered_files_info:
        if (f_info['format'] == 'unknown'):
            pass
        else:
            num_valid_filtered_files += 1

    custom_data['num_valid_filtered_files'] = num_valid_filtered_files

    num_valid_indel_files = 0
    for f_info in indel_files_info:
        if (f_info['format'] == 'unknown'):
            pass
        else:
            num_valid_indel_files += 1

    custom_data['num_valid_indel_files'] = num_valid_indel_files


    custom_data['dirs_info'] = dirs_info

    #custom_data['preprocessed_files'] = preprocessed_files_info
    custom_data['split_files'] = split_files_info
    custom_data['filtered_files'] = filtered_files_info
    custom_data['indel_files'] = indel_files_info


    return render_to_response('preprocess_old.html', custom_data,
                              context_instance=RequestContext(request))

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
    
    progress_texts = {'P':'Pending','A':'Importing','C':'Completed','F':'Err - Failed','M':'Err - Duplicate','X':'Err - Exception'}
    
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
               if (file_log.status == 'A'):
                   print ('recs read: ',file_log.records_read, ' base count: ',file_log.base_count, 'res: ',file_log.records_read * 1.0 / file_log.base_count * 100.0)
                   perc_complete = 0.0 if file_log.base_count == 0 else file_log.records_read * 1.0 / file_log.base_count * 100.0
                   file_progress_dict[os.path.split(batch_file)[1]] = file_log.status + "%.1f %%" % perc_complete  #str(perc_complete) #(file_log.records_read)
               else:    
                   file_progress_dict[os.path.split(batch_file)[1]] = file_log.status  
            except ChromosomeBatchImportLog.DoesNotExist:
                file_progress_dict[os.path.split(batch_file)[1]] = 'P' 
            except ChromosomeBatchImportLog.MultipleObjectsReturned:
                file_progress_dict[os.path.split(batch_file)[1]] = 'M'
            except:
                file_progress_dict[os.path.split(batch_file)[1]] = 'X'
            
              
    else:
        latest_batch = ChromosomeBatchImportProcess.objects.latest_finished_batch()
        if latest_batch is None:
            messages.info(request,'No pending, running or completed imports',extra_tags='html_safe alert alert-info')
        else: 
            if (latest_batch.batch_status == 'C'):
                successful_files = 0
                files_in_batch = latest_batch.chromosomebatchimportlog_set.all()
                if (files_in_batch is None):
                    messages.info(request,'No files in batch to import',extra_tags='html_safe alert alert-info')
                else:
                    for f in files_in_batch:
                        if f.status == 'C':
                            successful_files +=1
                if (successful_files == len(files_in_batch)):       
                    messages.success(request, 'Import(s) completed! ' + str(successful_files) + ' files succesfully imported',extra_tags='html_safe alert alert-success')
                else:
                    messages.warning(request, 'Import(s) completed. ' + str(successful_files) + ' / ' + str(len(files_in_batch)) + '  files successfully imported. ' + str(len(files_in_batch) - successful_files) + ' failed',extra_tags='html_safe alert alert-warning')
            else:    
                messages.error(request, 'Import(s) failed',extra_tags='html_safe alert alert-danger')
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
           
        if ((status[:1] == 'A') or (status == 'C')):
            # don't attempt to read, already open or alreast removed from pending imports folder
            file_info = {}
            print ('status: ',status)
            if (status[:1] == 'A'):
                print ('prog text: ',progress_texts[status[:1]])
                file_info['import_status'] = progress_texts[status[:1]] 
                file_info['import_perc_complete'] = status[1:]
            else:    
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
        if (latestBatchLog.status == 'C'):
            pass
        else:
            while not (latestBatchLog.status == 'C'): 
               latestBatchLog.delete()
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
 

def _get_file_info(request,fname = '',pre=False, subdir='_', type='_', verbose=0):
    from os.path import join
    verbose = int(verbose)

    also_retrieve_chromosomes = False
    also_retrieve_summary_flags = False


    if pre:
        mypath = settings.PSEUDOBASE_CHROMOSOME_RAW_DATA_VCF_PREFIX
        if subdir == '_':
            pass
        else:
            mypath = join(mypath,subdir)
        if type == '_':
            pass
        else:
            mypath = join(mypath, type)

        if verbose >= 1:
            also_retrieve_chromosomes = True
        if verbose >= 2:
            also_retrieve_summary_flags = True

    else:
        mypath = settings.PSEUDOBASE_CHROMOSOME_RAW_DATA_PENDING_PREFIX  #'raw_data/chromosome/pending_import/'
    
    response_data = {}
    error = ''

#    current_batches = ChromosomeBatchImportProcess.objects.current_batches() #ChromosomeBatchImportProcess.objects.filter(Q(batch_status='P') | Q(batch_status='I'))   
#    if (len(current_batches) > 0):
#       response_data = {'error':'Batch in progress','files_info':[]}
#       return HttpResponse(json.dumps(response_data), content_type="application/json") 
#    
#    
#    from os import listdir
#    from os.path import isfile, join
#    files = [f for f in listdir(mypath) if isfile(join(mypath, f))]
#   
#    
#    files_info = []
#    for f in files:


    
    try:
        c_importer = ChromosomeImporter(join(mypath, fname))
        file_info = c_importer.get_info(incl_rec_count = True,incl_all_chromosomes=also_retrieve_chromosomes, incl_all_summary_flags=also_retrieve_summary_flags)
    except Exception as e:   
        file_info = {}
        error = str(e)
        return HttpResponse(status=404)
           
    response_data = {'error':error,'file_info':file_info}
    return HttpResponse(json.dumps(response_data), content_type="application/json")


def audit(request):
    log.info('In Audit')
    custom_data = {}
    proj_data_folder = settings.PSEUDOBASE_CHROMOSOME_DATA_ROOT
    custom_data['project_folder'] = proj_data_folder

    from os import listdir
    from os.path import isfile, join, getsize
    files = [f for f in listdir(proj_data_folder) if isfile(join(proj_data_folder, f))]
    directories = [d for d in listdir(proj_data_folder) if not isfile(join(proj_data_folder,d))]
    seq_files = [f for f in files if len(f.split('.')) == 1]
    cov_files = [f for f in files if ( (len(f.split('.')) > 1) and (f.split('.')[1] == 'coverage'))]
    ind_files = [f for f in files if ((len(f.split('.')) > 1) and (f.split('.')[1] == 'index'))]


    file_tab = [{'file_tag': f, 'file_size': getsize(join(proj_data_folder,f)) / 1000000} for f in seq_files]

    for f in file_tab:
        try:
            if (f['file_tag'] + '.coverage') in cov_files:
                f['cov'] = 'Y'
            else:
                f['cov'] = 'N'
            if (f['file_tag'] + '.index') in ind_files:
                f['ind'] = 'Y'
            else:
                f['ind'] = 'N'
            chrBase = ChromosomeBase.objects.get(file_tag=f['file_tag'])
            f['chrom'] = chrBase.chromosome.name
            f['strain'] = chrBase.strain.name
            f['rel'] = chrBase.strain.release.name
            f['is_ref'] = 'Y' if chrBase.strain.is_reference else 'N'

        except:
            f['strain'] = 'Orphan'
            f['chrom'] = ''
            f['is_ref'] = ''


    file_tab.sort(key=lambda x:  (0 if x['is_ref'] == 'Y' else 1, x['strain'], x['chrom']))

    custom_data['files'] = file_tab
    custom_data['directories'] = directories

    return render_to_response('audit.html', custom_data,
                              context_instance=RequestContext(request))

def handle_uploaded_files(abspath, files):
    for i, file in enumerate(files):
        with open(os.path.join(abspath, file.name), 'wb+') as destination:
            for chunk in file.chunks():
                destination.write(chunk)


def preprocess_progress(request):
    mypath = settings.PSEUDOBASE_CHROMOSOME_RAW_DATA_VCF_PREFIX  # 'raw_data/chromosome/pending_import/'
    abspath = os.path.abspath(mypath)

    progress_texts = {'P': 'Pending', 'A': 'Importing', 'C': 'Completed', 'F': 'Err - Failed', 'M': 'Err - Duplicate',
                      'X': 'Err - Exception'}

    current_batches = ChromosomeBatchPreprocess.objects.current_batches()  # ChromosomeBatchImportProcess.objects.filter(Q(batch_status='P') | Q(batch_status='I'))
    if (len(current_batches) > 0):
        current_batch = current_batches[0]
        # current_batch_import_file_logs = current_batch.chromosomebatchimportlog_set.all()
        file_progress_dict = {}
        batch_file_list = [batch_file.strip() for batch_file in current_batch.original_request.split('\n')]

        progress_list = json.loads(current_batch.final_report)

    else:
#        messages.info(request, 'No running batches', extra_tags='html_safe alert alert-info')
#        progress_list = []
#        return redirect(autoimport)

        latest_batch = ChromosomeBatchPreprocess.objects.latest_finished_batch()
        if latest_batch is None:
            messages.info(request, 'No pending, running or completed preprocess runs', extra_tags='html_safe alert alert-info')
        else:
            if (latest_batch.batch_status == 'C'):
                successful_files = 0
                progress_list = json.loads(latest_batch.final_report)
                if (len(progress_list) == 0):
                    messages.info(request, 'No files in batch to preprocess', extra_tags='html_safe alert alert-info')
                else:
                    for prog_rec in progress_list:
                        if prog_rec['status'] == 'Complete':
                            successful_files += 1
                batch_file_list = [batch_file.strip() for batch_file in latest_batch.original_request.split('\n')]

                if (successful_files == len(batch_file_list)):
                    messages.success(request,
                                     'Preprocessing completed! ' + str(successful_files) + ' files succesfully preprocessed',
                                     extra_tags='html_safe alert alert-success')
                else:
                    messages.warning(request, 'Preprocessing completed. ' + str(successful_files) + ' / ' + str(
                        len(batch_file_list)) + '  files successfully preprocessed. ' + str(
                        len(batch_file_list) - successful_files) + ' failed', extra_tags='html_safe alert alert-warning')
            else:
                messages.error(request, 'Preprocess failed', extra_tags='html_safe alert alert-danger')
            return redirect(preprocess)

    custom_data = {}
    custom_data['tab'] = 'Preprocess Progress'

    custom_data['pending_preprocess_path'] = abspath


    custom_data['batch_file_list'] = batch_file_list
    custom_data['progress_list'] = progress_list
    custom_data['batch_file_filenames'] = [os.path.split(file_name)[1] for file_name in batch_file_list]


    return render_to_response('preprocess_progress.html', custom_data,
                              context_instance=RequestContext(request))


def preprocess(request):
    log.info('In Preprocess')

    verbose = int(request.GET.get('verbose', '0'))

    custom_data = {}

    mypath = settings.PSEUDOBASE_CHROMOSOME_RAW_DATA_VCF_PREFIX
    abspath = os.path.abspath(mypath)

    from os import listdir
    from os.path import isfile, join
    custom_data['pending_preprocess_path'] = abspath


    if request.method == 'POST':

        if 'uploadfiles' in request.POST:
            form = chromosome.forms.UploadForm(request.POST, request.FILES)
            if form.is_valid():
                files = request.FILES.getlist('upload_file_field')
                handle_uploaded_files(abspath, files)
                custom_data['files'] = files
                custom_data['form'] = form
                if len(files) == 0:
                    messages.info(request, 'Please choose files for upload first!', extra_tags='html_safe alert alert-info')
                print('files: ',files)
        elif 'preprocessfiles' in request.POST :
           form = chromosome.forms.UploadForm(request.POST)
           selected_values = request.POST.getlist('preprocess_files')
           print('sel values: ', selected_values)
           custom_data['form'] = form

           # Start transaction management.
           transaction.commit_unless_managed()
           transaction.enter_transaction_management()
           transaction.managed(True)
           try:
               if (len(selected_values) == 0):
                   raise Exception('No files selected for import')

               current_batches = ChromosomeBatchPreprocess.objects.current_batches()
               if (len(current_batches) > 0):
                   raise Exception('Batch preprocess already in process. Please wait ')

               bp = ChromosomeBatchPreprocess(submitted_at=django.utils.timezone.now(), batch_status='P')

               bp.set_orig_request_from_filenames(selected_values)
               bp.final_report = json.dumps([])

               bp.save()

               # Finalize the transaction and close the db connection.
               transaction.commit()
               transaction.leave_transaction_management()
               connection.close()
               messages.success(request, str(len(selected_values)) + ' files selected for preprocess. \nPlease wait for preprocessing to auto start',
                                extra_tags='html_safe alert alert-success')
               return redirect(preprocess_progress)
           except Exception as e:
               transaction.rollback()
               transaction.leave_transaction_management()

               messages.error(request, 'Batch import process failed: ' + str(e),
                              extra_tags='html_safe alert alert-danger')
               return redirect(preprocess)

    current_batches = ChromosomeBatchPreprocess.objects.current_batches()  # ChromosomeBatchImportProcess.objects.filter(Q(batch_status='P') | Q(batch_status='I'))
    if (len(current_batches) > 0):
        return redirect(preprocess_progress)

    form = chromosome.forms.UploadForm()
    custom_data['form'] = form

    uploaded_files = [f for f in listdir(mypath) if isfile(join(mypath, f))]
    directories = [d for d in listdir(mypath) if not isfile(join(mypath, d))]

    files_info = []
    for f in uploaded_files:
        c_importer = ChromosomeImporter(join(mypath, f))
        file_info = c_importer.get_info(incl_rec_count=False)

        if 'file_size' in file_info:
            file_info['file_size_MB'] = "%.2fMB" % file_info['file_size']

        if file_info['format'] == 'unknown':
            pass
        else:
            files_info.append(file_info)

    num_valid_pending_preprocess_files = 0
    for f_info in files_info:
        if (f_info['format'] == 'unknown'):
            pass
        else:
            num_valid_pending_preprocess_files += 1

    custom_data['num_valid_pending_preprocess_files'] = num_valid_pending_preprocess_files
    custom_data['uploaded_files'] = files_info

    dirs_info = []

    preprocessed_files_info = []
    pending_import_files_info = []

    # Handle pending import files (ie already preprocessed/split):
    from os import listdir
    from os.path import isfile, join
    pending_import_path = settings.PSEUDOBASE_CHROMOSOME_RAW_DATA_PENDING_PREFIX  # 'raw_data/chromosome/pending_import/'
    pending_import_abspath = os.path.abspath(pending_import_path)
    custom_data['pending_import_path'] = pending_import_abspath
    pending_import_files = [f for f in listdir(pending_import_abspath) if isfile(join(pending_import_abspath, f))]

    pending_import_files_info = []
    for f in pending_import_files:
        c_importer = ChromosomeImporter(join(pending_import_abspath, f))
        pending_import_file_info = c_importer.get_info(incl_rec_count=False)

        if 'file_size' in pending_import_file_info:
            pending_import_file_info['file_size_MB'] = "%.2fMB" % pending_import_file_info['file_size']

        pending_import_files_info.append(pending_import_file_info)

    num_valid_pending_import_files = 0
    for pending_import_f_info in pending_import_files_info:
        if (pending_import_f_info['format'] == 'unknown'):
            pass
        else:
            num_valid_pending_import_files += 1
    custom_data['num_valid_pending_import_files'] = num_valid_pending_import_files

    custom_data['pending_import_files'] = pending_import_files_info

    split_files_info  = [] # No longer used, now uses pending_import_files_info
    filtered_files_info = []
    indel_files_info = []

    for d in directories:
        if d[:1] == 'D':
            dir_info = {}
            dir_info['strain'] = d

            strain_dir = join(mypath, d)
            # strain_files = [f for f in listdir(strain_dir) if isfile(join(strain_dir,f))]
            #
            # for f in strain_files:
            #     c_importer = ChromosomeImporter(join(strain_dir, f))
            #     preprocessed_file_info = c_importer.get_info(incl_rec_count=False)
            #
            #     if 'file_size' in preprocessed_file_info:
            #         preprocessed_file_info['file_size_MB'] = "%.2fMB" % preprocessed_file_info['file_size']
            #
            #     preprocessed_file_info['strain'] = d
            #     preprocessed_file_info['type'] = 'Split'
            #     preprocessed_files_info.append(preprocessed_file_info)

            strain_subdirectories = [d_sub for d_sub in listdir(strain_dir) if not isfile(join(strain_dir, d_sub))]
            # dir_info['split'] = len(strain_files)

            for sub_dir in strain_subdirectories:
                strain_subdir = join(strain_dir, sub_dir)
                strain_subdir_files = [f for f in listdir(strain_subdir) if
                                       isfile(join(strain_subdir, f))]

                for f in strain_subdir_files:
                    c_importer = ChromosomeImporter(join(strain_subdir, f))
                    preprocessed_file_info = c_importer.get_info(incl_rec_count=False)

                    if 'file_size' in preprocessed_file_info:
                        preprocessed_file_info['file_size_MB'] = "%.2fMB" % preprocessed_file_info['file_size']

                    preprocessed_file_info['strain'] = d
                    preprocessed_file_info['type'] = sub_dir
                    if sub_dir == 'split':
                        split_files_info.append(preprocessed_file_info)
                    elif sub_dir == 'filtered':
                        filtered_files_info.append(preprocessed_file_info)
                    else:
                        indel_files_info.append(preprocessed_file_info)
                    # preprocessed_files_info.append(preprocessed_file_info)
                # if sub_dir == 'filtered':
                #     strain_filtered_dir = join(strain_dir,sub_dir)
                #     strain_filtered_files = [f for f in listdir(strain_filtered_dir) if isfile(join(strain_filtered_dir, f))]
                #     dir_info['filtered'] = len(strain_filtered_files)
                #
                # elif sub_dir == 'indels':
                #     strain_indels_dir = join(strain_dir, sub_dir)
                #     strain_indels_files = [f for f in listdir(strain_indels_dir) if   isfile(join(strain_indels_dir, f))]
                #     dir_info['indels'] = len(strain_indels_files)
            dirs_info.append(dir_info)

    num_valid_split_files = 0
    for f_info in split_files_info:
        if (f_info['format'] == 'unknown'):
            pass
        else:
            num_valid_split_files += 1

    custom_data['num_valid_split_files'] = num_valid_split_files

    num_valid_filtered_files = 0
    for f_info in filtered_files_info:
        if (f_info['format'] == 'unknown'):
            pass
        else:
            num_valid_filtered_files += 1

    custom_data['num_valid_filtered_files'] = num_valid_filtered_files

    num_valid_indel_files = 0
    for f_info in indel_files_info:
        if (f_info['format'] == 'unknown'):
            pass
        else:
            num_valid_indel_files += 1

    custom_data['num_valid_indel_files'] = num_valid_indel_files

    custom_data['dirs_info'] = dirs_info

    # custom_data['preprocessed_files'] = preprocessed_files_info
    custom_data['split_files'] = split_files_info
    custom_data['filtered_files'] = filtered_files_info
    custom_data['indel_files'] = indel_files_info

    custom_data['verbose'] = verbose

    return render_to_response('preprocess.html', custom_data,
                              context_instance=RequestContext(request))
