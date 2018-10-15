'''Views for the common application.'''

import os

from django.shortcuts import render_to_response,redirect
from django.template import RequestContext
from django.contrib import messages
from django.http import HttpResponse

import chromosome.forms
from chromosome.models import ChromosomeBase, ChromosomeImporter, ChromosomeImportLog

    
def import_files(request):
    if request.method == 'POST':
        print ('posttt')    
        form = chromosome.forms.ImportForm(request.POST)
        print('instantiated form'   )
        selected_values = request.POST.getlist('import_files')
        print ('sel vals: ',selected_values)
        return HttpResponse("Importing..." + str(selected_values))
        if form.is_valid():
           print ('form is valid')   
           cd = form.cleaned_data
           print ('cd: ',cd['import_files'])
        else:
           print ('failed validation: ',form.cleaned_data) 
    
    custom_data = {}
    custom_data['tab'] = 'Import'
    
    from os import listdir
    from os.path import isfile, join
    mypath = './raw_data/chromosome/pending_import'
    abspath = os.path.abspath(mypath)
    custom_data['pending_import_path'] = abspath
    onlyfiles = [f for f in listdir(mypath) if isfile(join(mypath, f))]
   
    
    onlyfiles_info = []
    for f in onlyfiles:
        c_importer = ChromosomeImporter(join(mypath, f))
        file_info = c_importer.get_info(incl_rec_count = False)
        
        if 'file_size' in file_info:
           file_info['file_size_MB'] = "%.2fMB" % file_info['file_size']
        onlyfiles_info.append(file_info)
    
    custom_data['pending_files'] = onlyfiles_info  
    
    #Get recent completed imports
    custom_data['recent_imports'] = ChromosomeImportLog.objects.all().order_by('-end')
        
    
    return render_to_response('import.html', custom_data,
      context_instance=RequestContext(request))   
    
def import_file(request,fname=''):
    custom_data = {}
    custom_data['tab'] = 'Import File'
    custom_data['fname'] = fname
    print ('fname: ',fname)
    
    mypath = './raw_data/chromosome/pending_import'
    from os.path import join
    fullfile = join(mypath, fname)
    
    try:
        c_importer = ChromosomeImporter(fullfile)
        file_info = c_importer.get_info(incl_rec_count = True)
        
        custom_data['file_info'] = file_info
    
        c_importer.import_data()
        
        print ('info: ',file_info)
        messages.success(request, 'File imported successfully!',extra_tags='html_safe alert alert-success')
        return redirect(import_files)
        
    except Exception as e: 
        print ('Import failed: ',e)
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
        
        latestLog = ChromosomeImportLog.objects.all().order_by('-id')[0]
        fpath = latestLog.file_path
        print ('latest log: ',fpath)
        
        sourcepath = './raw_data/chromosome'
        destpath = './raw_data/chromosome/pending_import'
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
    latestLog.delete()
    messages.success(request, 'Latest deleted successfully!',extra_tags='html_safe alert alert-success')
    return redirect(import_files)
 

