'''Views for the common application.'''

import os

import django.utils.timezone
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.conf import settings
from django.contrib.sites.models import RequestSite
from django.http import Http404

# for jbrowse rest api
from django.http import HttpResponse
import json

import gene.forms
import chromosome.forms
from chromosome.models import ChromosomeBase
from gene.models import Gene, GeneSymbol, GeneBatchProcess
from common.models import Species, Strain
from os import listdir
from os.path import isfile, join

import logging
#logging.basicConfig(filename='test_logging_rbm.log',level=logging.DEBUG)
log = logging.getLogger(__name__)


def _render_search_forms(request,
  chromosome_form=chromosome.forms.SearchForm(),
  gene_form=gene.forms.SearchForm()):
    '''Render the default search page with both search forms.'''

    session_search_tab = request.session.get('session_search_tab', 'gene')

    custom_data = {}
    custom_data['chromosome_form'] = chromosome_form
    custom_data['gene_form'] = gene_form
    custom_data['tab'] = 'Home'
    custom_data['session_search_tab'] = session_search_tab

  
    # The StatCounter should only display when debugging is not enabled
    custom_data['display_counter'] = not settings.DEBUG
  
    search_page = 'index_search_chrom.html' if (session_search_tab == 'chromosome') else 'index_search_gene.html'
    return render_to_response(search_page, custom_data,
      context_instance=RequestContext(request))


def _render_chromosome_search(request):
    '''Render the results of a chromosome search.'''

    log.info('In _render_chrom_search.')
    custom_data = {}
    form = chromosome.forms.SearchForm(request.POST)
    if form.is_valid():
        log.info('In _render_chrom_search. Valid form.. Chr: %s From: %s To: %s Aligned?: %s Species: %s' % (form.cleaned_data['chromosome'].name, form.cleaned_data['position'][0], form.cleaned_data['position'][1], form.cleaned_data['show_aligned'], form.cleaned_data['species']) )
        custom_data['fasta_objects'] = ChromosomeBase.multi_strain_fasta(
          form.cleaned_data['chromosome'],
          form.cleaned_data['species'],
          form.cleaned_data['position'][0],
          form.cleaned_data['position'][1],
          form.cleaned_data['show_aligned'])
        return render_to_response('chromosome_fasta.html', custom_data,
          context_instance=RequestContext(request))
    log.warning('In _render_chrom_search. Not valid form')
    return _render_search_forms(request, chromosome_form=form)

def assemble_jbrowse_chromosome_query_data(request):

    custom_data = {}
    form = chromosome.forms.SearchForm(request.POST)
    if form.is_valid():
        custom_data['chr'] = form.cleaned_data['chromosome'].name
        custom_data['species'] = []
        custom_data['strain_names'] = []
        for species in form.cleaned_data['species']:
            for i, strain in enumerate(species.strain_set.all().order_by('name')):
                if settings.JBROWSE_INIT_MAX_STRAINS_SHOWN_PER_SPECIES is None:
                    pass
                else:
                    if i >= settings.JBROWSE_INIT_MAX_STRAINS_SHOWN_PER_SPECIES:
                        break
                custom_data['strain_names'].append(strain.name)
                for strain_symbol in strain.strainsymbol_set.all():
                    custom_data['species'].append(strain_symbol.symbol)
            #custom_data['species'].extend([x.strainsymbol_set.all()[0].symbol for x in species.strain_set.all()])
        #custom_data['species'] = [x.symbol for x in form.cleaned_data['species']]
        custom_data['pos_from'] = form.cleaned_data['position'][0]
        custom_data['pos_to'] = form.cleaned_data['position'][1]
        vcf_tracks = [x + '_VCF' for x in custom_data['species']]
        custom_data['tracks_query'] = 'tracks=ref,genes,' + ','.join(vcf_tracks)

        custom_data['jbrowse_location'] = settings.JBROWSE_LOCATION
        custom_data['jbrowse_rel_location'] = settings.JBROWSE_REL_LOCATION

    return custom_data

def assemble_jbrowse_gene_query_data(request):

    custom_data = {}
    import gene.forms
    form = gene.forms.SearchForm(request.POST, request.FILES)

    if form.is_valid():
        try:
            symbol = GeneSymbol.objects.get(symbol=form.cleaned_data['gene'])
            flybase_id = symbol.flybase_ID()
            strain_genes = Gene.objects.filter(import_code=flybase_id).order_by('-strain__is_reference')
            gene = strain_genes[0]
            custom_data['chr'] = gene.chromosome.name
            custom_data['species'] = []
            for species in form.cleaned_data['species']:
                for i, strain in enumerate(species.strain_set.all().order_by('name')):
                    if settings.JBROWSE_INIT_MAX_STRAINS_SHOWN_PER_SPECIES is None:
                        pass
                    else:
                        if i >= settings.JBROWSE_INIT_MAX_STRAINS_SHOWN_PER_SPECIES:
                            break
                    for strain_symbol in strain.strainsymbol_set.all():
                        custom_data['species'].append(strain_symbol.symbol)
                #custom_data['species'].extend([x.strainsymbol_set.all()[0].symbol for x in species.strain_set.all()])
            #custom_data['species'] = [x.symbol for x in form.cleaned_data['species']]
            custom_data['pos_from'] = int(gene.start_position)
            custom_data['pos_to'] = int(gene.end_position)
            vcf_tracks = [x + '_VCF' for x in custom_data['species']]
            custom_data['tracks_query'] = 'tracks=ref,genes,' + ','.join(vcf_tracks)
            custom_data['jbrowse_location'] = settings.JBROWSE_LOCATION
            custom_data['jbrowse_rel_location'] = settings.JBROWSE_REL_LOCATION
        except:
            pass

    return custom_data

def assemble_general_browse_query_data():
    custom_data = {}
    custom_data['chr'] = '2'
    custom_data['pos_from'] = 1
    custom_data['pos_to'] = 100
    custom_data['species'] = []
    #all_strains = Strain.objects.all()
    # for strain in Strain.objects.all():
    try:
      strain = Strain.objects.get(strainsymbol__symbol="AFC12")   # Only select first strain for general browse (users can then select rqd strains within JBrowse)
    except:
      strain = Strain.objects.all()[0]

    for strain_symbol in strain.strainsymbol_set.all():
        custom_data['species'].append(strain_symbol.symbol)
    vcf_tracks = [x + '_VCF' for x in custom_data['species']]
    custom_data['tracks_query'] = 'tracks=ref,genes,' + ','.join(vcf_tracks)
    custom_data['jbrowse_location'] = settings.JBROWSE_LOCATION
    custom_data['jbrowse_rel_location'] = settings.JBROWSE_REL_LOCATION
    return custom_data


def _submit_new_gene_batch(request, form):
    '''Submit a new batch gene search for processing.'''
    log.info('Submitting gene batch search. '+ str(form.cleaned_data))
    gene_batch = GeneBatchProcess()
    gene_batch.submitted_at = django.utils.timezone.now()
    gene_batch.original_species  = ','.join(
      ['%s' % i.pk for i in form.cleaned_data['species']])
    email, symbols = form.cleaned_data['gene_batch_file']
    gene_batch.submitter_email = email
    gene_batch.original_request = ''.join(symbols)
    gene_batch.delivery_tag = GeneBatchProcess.generate_unique_tag()
    gene_batch.show_aligned = form.cleaned_data['show_aligned']
    gene_batch.save()
  
    custom_data = {}  
    custom_data['delivery_tag'] = gene_batch.delivery_tag
    custom_data['full_delivery_url'] = gene_batch.full_delivery_url(
      site=RequestSite(request).domain)
    return render_to_response('gene_batch_submission.html', custom_data,
      context_instance=RequestContext(request))


def _render_gene_search(request):
    '''Render the results of a gene search.'''

    custom_data = {}
    form = gene.forms.SearchForm(request.POST, request.FILES)

    if not form.is_valid():
        # If the submitted data has a form validation problem, skip the rest.
        return _render_search_forms(request, gene_form=form)

    if len(request.FILES) == 1:
        return _submit_new_gene_batch(request, form=form)

    try:
        log.info('In _render_gene_search. Valid form.. Gene: %s Aligned?: %s Species: %s' % (form.cleaned_data['gene'], form.cleaned_data['show_aligned'], form.cleaned_data['species']) )
        symbols = GeneSymbol.objects.get(
          symbol=GeneSymbol.normalize(form.cleaned_data['gene'])).all_symbols()
        fasta_objects = Gene.multi_gene_fasta(form.cleaned_data['gene'],
          form.cleaned_data['species'],form.cleaned_data['show_aligned'])
    except GeneSymbol.DoesNotExist:
        return render_to_response('gene_fasta.html',
          {'errors': 'Gene identified "%s" does not exist in Pseudobase.' % \
            form.cleaned_data['gene']}, 
          context_instance=RequestContext(request))

    custom_data['fasta_objects'] = fasta_objects
    return render_to_response('gene_fasta.html', custom_data,
      context_instance=RequestContext(request))


def _convert_bytes(n):
    '''Convert byte count into a human readable version.'''
    
    K, M, G, T = 1 << 10, 1 << 20, 1 << 30, 1 << 40
    if n >= T:
        return '%.1fTB' % (float(n) / T)
    elif n >= G:
        return '%.1fGB' % (float(n) / G)
    elif n >= M:
        return '%.1fMB' % (float(n) / M)
    elif n >= K:
        return '%.1f KB' % (float(n) / K)
    else:
        return '%dB' % n



def index(request):
    '''Handle requests for the main "search" page and validate submissions.'''
    search_tab = request.GET.get('search_tab','')
    if search_tab != '':
       request.session['session_search_tab'] = search_tab 
 
    print ('in index')
    log.info('In  index')

    if request.method == 'POST':
        print ('Posting')
        log.info('Posting')

        if 'chrom_browse_type' in request.POST:
            form = chromosome.forms.SearchForm(request.POST)
            if form.is_valid():
                custom_data = assemble_jbrowse_chromosome_query_data(request)
                log.info('JBrowsing to Chrom region: %s' % custom_data)
                return render_to_response('test_jb.html', custom_data,
                                          context_instance=RequestContext(request))
            else:
                return _render_search_forms(request, chromosome_form=form)
        elif 'gene_browse_type' in request.POST:
            form = gene.forms.SearchForm(request.POST, request.FILES)
            if form.is_valid():
                custom_data = assemble_jbrowse_gene_query_data(request)
                log.info('JBrowsing to Gene: %s' % custom_data)
                return render_to_response('test_jb.html', custom_data,
                                          context_instance=RequestContext(request))
            else:
                return _render_search_forms(request, gene_form=form)

        elif 'chrom_search_type' in request.POST: #['search_type'] ==  'Quick search': #'Search by chromosome':
            log.info('In index. Showing results. chrom search type: %s' % request.POST['chrom_search_type'])
            return _render_chromosome_search(request)
        elif 'gene_search_type' in request.POST: # ['search_type'] == 'Search by gene':
            log.info('In index. Showing results. gene search type: %s' % request.POST['gene_search_type'])
            return _render_gene_search(request)
    return _render_search_forms(request)

def info(request):
    custom_data = {}
    custom_data['tab'] = 'More Info'
    
    all_species = Species.objects.all()
    species_tab = []
    for species in all_species:
        lines = Strain.objects.filter(species = species)
        species_tab.append({'name':species.name,'num_lines':len(lines),'lines':lines})
        
    custom_data['species_tab'] = species_tab

    return render_to_response('info.html', custom_data,
      context_instance=RequestContext(request))


def browse(request):
    custom_data = assemble_general_browse_query_data()
    custom_data['tab'] = 'Browse'

    return render_to_response('test_jb.html', custom_data,
                              context_instance=RequestContext(request))


def about(request):
    custom_data = {}
    custom_data['tab'] = 'About'

    return render_to_response('about.html', custom_data,
                              context_instance=RequestContext(request))

def contact(request):
    custom_data = {}
    custom_data['tab'] = 'Contact'

    return render_to_response('contact.html', custom_data,
                              context_instance=RequestContext(request))


def delivery(request, code):
    '''Handle requests for the "delivery" page.'''

    # Check to see if code maps to an actual delivery.
    try:
        batch_process = GeneBatchProcess.objects.get(delivery_tag=code)
    except GeneBatchProcess.DoesNotExist:
        raise Http404

    # The code exists, so check to see if the results are present.
    if batch_process.batch_status == 'C':
      delivery_file = os.path.join(settings.PSEUDOBASE_DELIVERY_ROOT,
        batch_process.delivery_tag, settings.PSEUDOBASE_RESULTS_FILENAME)
      if os.path.exists(delivery_file):
          # The results exist, so display the appropriate delivery page.
          return render_to_response('gene_delivery_ready.html', {
              'results_url': batch_process.full_delivery_url(site='',
                protocol=''),
              'expiration': batch_process.expiration,
              'results_size': _convert_bytes(os.path.getsize(delivery_file))}, 
            context_instance=RequestContext(request))
    else:
        return render_to_response('gene_delivery_not_ready.html', {}, 
          context_instance=RequestContext(request))

def format_log(log_type, log_line):
    log_line_data = log_line.split(' ')
    if len(log_line_data) < 3:
        formatted_log_line = ['','',' '.join(log_line_data)]
    else:
        formatted_log_line = [log_line_data[0], log_line_data[1], log_type, ' '.join(log_line_data[2:])]
    return formatted_log_line

def logs(request):
    log.info('In logs')

    log_dir = join(settings.BASE_DIR, settings.LOG_FILE_PREFIX)
    files = [f for f in listdir(log_dir) if isfile(join(log_dir, f))]
    files_info = []

    custom_data = {'files': files}

    custom_data['logs'] = []

    for f in files:
        full_name = join(log_dir, f)
        with open(full_name) as file:
             data = file.read()
             data_lines = data.split('\n')
             print('data: ',len(data_lines))
             for line in data_lines:
                 line_data = line.split(' ')
                 if 'Valid form' in line:
                    if 'render_chromosome_search' in line:
                        custom_data['logs'].append(format_log('Online Chrom Search', line))
                    elif 'render_gene_search' in line:
                        custom_data['logs'].append(format_log('Online Gene Search', line))
                 elif 'JBrowsing to Gene' in line:
                     custom_data['logs'].append(format_log('JBrowse to gene', line))
                 elif 'JBrowsing to Chrom' in line:
                     custom_data['logs'].append(format_log('JBrowse to chrom region', line))
                 elif 'Submitting gene batch search' in line:
                     custom_data['logs'].append(format_log('Batch Gene Search', line))
    custom_data['logs'].reverse()

    return render_to_response('logs.html', custom_data,
                              context_instance=RequestContext(request))



def jb_stats_global(request):

    response_data = {"featureDensity": 0.02,"featureCount": 234235,"scoreMin": 87,"scoreMax": 87,"scoreMean": 42,"scoreStdDev": 2.1}

    return HttpResponse(json.dumps(response_data), content_type="application/json")

def jb_get_features(request,ref_name=''):
    start = int(request.GET.get('start', '0'))
    end = int(request.GET.get('end', '0'))
    strain = request.GET.get('strain', None)


    if strain is None:
        pass
    elif strain == 'Flg14':

    #tst_seq = "AAAACCCGATTGGC"
    #cig = "14M"
    #md = "8T5"

        ref_seq = "AAAACCCGTTTGGC"
        tst_start = 23

        tst_seq = "AAACCCGATTGAAGC"

        cig = "1M1D10M2I2M"
        md = "1^A6T5"

    elif strain == 'ARIZ':
        ref_seq = "AAAACCCGTTTGGC"
        tst_start = 23

        tst_seq = "AAAATCCGTTTGGC"

        cig = "14M"
        md = "4C9"

    elif strain == 'Flg16':
        ref_seq = "TAGCCCCCCCCCCCCCCCCCCCCCCCCCCCCCA"
        tst_seq = "TAGCCCCCCCACCCCCCCCCCCCCCCCCCCCCA"
        tst_start = 45
        cig = "33M"
        md = "10C22"


    tst_end = tst_start + len(ref_seq)



    if start < tst_end and  end > tst_start:
        response_data = {
          "features": [
            {"type":"match","name":"test","id":"test1","seq": tst_seq, "seq_length":len(tst_seq),"length_on_ref":len(ref_seq),"unmapped":False,"qc_failed":False,"duplicate":False,"secondary_alignment":False,"supplementary_alignment":False,"score":0,"template_length":0,"MQ":0,"start": tst_start, "end":tst_end , "strand":1,"tags":["seq","CIGAR","MD","length_on_ref","seq_length","unmapped","qc_failed","duplicate","secondary_alignment","supplementary_alignment","template_length","MQ"],"cigar":cig, "md":md}
          ]
        }
    else:
        response_data = {
            "features": [

            ]
        }

    return HttpResponse(json.dumps(response_data), content_type="application/json")

