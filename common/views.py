'''Views for the common application.'''

import os

import django.utils.timezone
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.conf import settings
from django.contrib.sites.models import RequestSite
from django.http import Http404

import gene.forms
import chromosome.forms
from chromosome.models import ChromosomeBase
from gene.models import Gene, GeneSymbol, GeneBatchProcess
from common.models import Species, Strain


def _render_search_forms(request,
  chromosome_form=chromosome.forms.SearchForm(),
  gene_form=gene.forms.SearchForm()):
    '''Render the default search page with both search forms.'''

    custom_data = {}
    custom_data['chromosome_form'] = chromosome_form
    custom_data['gene_form'] = gene_form
    custom_data['tab'] = 'Home'

  
    # The StatCounter should only display when debugging is not enabled
    custom_data['display_counter'] = not settings.DEBUG
  
    return render_to_response('index_search.html', custom_data,
      context_instance=RequestContext(request))


def _render_chromosome_search(request):
    '''Render the results of a chromosome search.'''
 
    custom_data = {}
    form = chromosome.forms.SearchForm(request.POST)
    if form.is_valid():
        custom_data['fasta_objects'] = ChromosomeBase.multi_strain_fasta(
          form.cleaned_data['chromosome'],
          form.cleaned_data['species'],
          form.cleaned_data['position'][0],
          form.cleaned_data['position'][1])
        return render_to_response('chromosome_fasta.html', custom_data,
          context_instance=RequestContext(request))
    return _render_search_forms(request, chromosome_form=form)


def _submit_new_gene_batch(request, form):
    '''Submit a new batch gene search for processing.'''

    gene_batch = GeneBatchProcess()
    gene_batch.submitted_at = django.utils.timezone.now()
    gene_batch.original_species  = ','.join(
      ['%s' % i.pk for i in form.cleaned_data['species']])
    email, symbols = form.cleaned_data['gene_batch_file']
    gene_batch.submitter_email = email
    gene_batch.original_request = ''.join(symbols)
    gene_batch.delivery_tag = GeneBatchProcess.generate_unique_tag()
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
        symbols = GeneSymbol.objects.get(
          symbol=GeneSymbol.normalize(form.cleaned_data['gene'])).all_symbols
        fasta_objects = Gene.multi_gene_fasta(form.cleaned_data['gene'],
          form.cleaned_data['species'])
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

    if request.method == 'POST':
        if request.POST['search_type'] == 'Search by chromosome':
            return _render_chromosome_search(request)
        elif request.POST['search_type'] == 'Search by gene':
            return _render_gene_search(request)
    return _render_search_forms(request)



def format_strain_collection_info(strain,include_chromosome_info = False):

    strain_info = ''

    try:
        if (strain.straincollectioninfo.year is not None):
            strain_info += ', collected: ' + str(strain.straincollectioninfo.year)
        if (len(strain.straincollectioninfo.info) > 0):
           strain_info += ', ' + strain.straincollectioninfo.info
    except:
        pass
    
    if (include_chromosome_info):
        chrom_bases = ChromosomeBase.objects.filter(strain = strain)
        strain_info += ' (' + str(len(chrom_bases)) + ' chromosome'
        if (len(chrom_bases) != 1):
            strain_info += 's'
        strain_info += ')'    
        
    
    return strain.name + strain_info
    

def info(request):
    custom_data = {}
    custom_data['tab'] = 'More Info'
    
    all_species = Species.objects.all()
    print ('all species',all_species)
    species_tab = []
    for species in all_species:
        lines = Strain.objects.filter(species = species)
        lines_tab = []  
        for line in lines:
            line_info = format_strain_collection_info(line)
            lines_tab.append(line_info)
        species_tab.append({'name':species.name,'num_lines':len(lines),'lines':lines_tab})
        
    custom_data['species_tab'] = species_tab
    print ('species_tab: ',species_tab)
        
        
    
    return render_to_response('info.html', custom_data,
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
