'''Models for the gene application.'''

import os
import random
import re
import string
import textwrap

from django.conf import settings
from django.db import models

from common.models import Strain, Chromosome
from common.models import BatchProcess, ImportLog

from chromosome.models import ChromosomeBase




class Gene(models.Model):
    '''Sequence Data and metadata about a particular gene sequence.'''
    
    strain = models.ForeignKey(Strain)
    chromosome = models.ForeignKey(Chromosome)
    start_position = models.PositiveIntegerField()
    end_position = models.PositiveIntegerField()
    import_code = models.CharField(max_length=255, db_index=True)
    bases = models.TextField() #(editable=False)

    def __str__(self):
        '''Define the string representation of this class of object.'''
        return '%s, %s, %s' % (self.chromosome.name, self.import_code, self.strain.name)


    def largest_transcript(self):
        mrnas = self.mrna_set.all()
        largest = None
        largest_size = -1
        for mrna in mrnas:
            len = mrna.cds_total_length()
            if len > largest_size:
                largest_size = len
                largest = mrna
        return largest

    def bases_for_largest_transcript(self):
        pass

    def fasta_header(self, delimiter='|'):
        '''Return a FASTA-compliant header containing sequence metadata.
        
        If delimiter is specified, it is used instead of the default.
        
        '''
        largest_transcript = self.largest_transcript()
        return r'>%s' % delimiter.join((self.strain.species.name,
          self.strain.name,
          '%s_%s %s' %(self.chromosome.name, self.start_position if largest_transcript is None else largest_transcript.start_position(), '' if largest_transcript is None else largest_transcript.name),
          self.symbols()))
  
    def fasta_bases(self, wrapped=True):
        '''Return the sequence data for the specified range.
      
        This data is retrieved from the data file.  It is generally wrapped
        to 75 characters for format compliance.
      
        '''

        largest_transcript = self.largest_transcript()
        if largest_transcript is None:
            bases = self.bases
        else:
            #ref_strain = Strain.objects.get(name__contains='refer',release__name__contain='3')
            bases = largest_transcript.bases_for_strain(self.strain)
    
        if wrapped:
            # We have to go through this little eval dance because the
            # "break_on_hyphens" keyword argument only exists in python 2.6+.
            try:
                eval('textwrap.TextWrapper(break_on_hyphens=False)')
                tw = textwrap.TextWrapper(width=75, break_on_hyphens=False)
            except TypeError:
                tw = textwrap.TextWrapper(width=75)
            return tw.wrap(bases)
        else:
            return bases

    def symbols(self):
        '''Return all symbols that represent this gene.'''
        return ','.join(
          GeneSymbol.objects.get(symbol=self.import_code).all_symbols())

    @staticmethod  
    def multi_gene_fasta(symbol, species):
        '''Generator which returns FASTA header/data individually.
        
        Provided with a gene symbol and an array of the species that should be
        queried, construct FASTA-compatible text output of all matching gene
        sequences.  This includes all GeneSymbols that are listed as
        translations.
        
        There can potentially be a lot of sequences for any given pair of
        gene and species.  We return a generator so that we don't have
        to store all those sequences (which can be large even individually) in
        memory for any longer than necessary.
        
        This method primarily handles the "search by gene" functionality from 
        the web interface.
        
        '''
    
        n_symbols = GeneSymbol.objects.get(
          symbol=GeneSymbol.normalize(symbol)).all_symbols()
        genes = Gene.objects.filter(strain__species__pk__in=species).filter(
          import_code__in=n_symbols).order_by('-strain__is_reference', 
            'strain__species__id', 'strain__name')
        for g in genes:
            yield (g.fasta_header(), g.fasta_bases())
    
    class Meta:
        '''Define Django-specific metadata.'''
        ordering = ('strain__species__pk', 'strain__name')


class MRNA(models.Model):
    name = models.CharField(max_length=255)
    gene = models.ForeignKey(Gene)

    def __str__(self):
        '''Define the string representation of this class of object.'''
        return '%s, %s' % (self.gene.import_code, self.name)

    class Meta:
        verbose_name_plural = 'mRNA Transcripts'

    def cds_total_length(self):
        cds_records = self.cds_set.all()
        tot_len = 0
        for rec in cds_records:
            tot_len += rec.length()

        return tot_len


    def cds_list(self):
        cds_list = []
        for cds in self.cds_set.all():
            cds_list.append([cds.start_position,cds.end_position])

        return cds_list

    def bases_for_strain(self,strain):
        bases_list = []
        cb = ChromosomeBase.objects.get(strain=strain,chromosome=self.gene.chromosome)
        for cds_range in self.cds_list():
            cds_bases = cb.fasta_bases(cds_range[0],cds_range[1])
            bases_list.extend(cds_bases)
        return ''.join(bases_list)


    def start_position(self):
        cds_list = self.cds_list()
        if len(cds_list) > 0:
            return cds_list[0][0]
        else:
            return -1

    def end_position(self):
        cds_list = self.cds_list()
        if len(cds_list) > 0:
            return cds_list[-1][-1]
        else:
            return -1

class CDS(models.Model):
    mRNA = models.ForeignKey(MRNA)
    start_position = models.PositiveIntegerField()
    end_position = models.PositiveIntegerField()
    num = models.PositiveIntegerField()

    def __str__(self):
        '''Define the string representation of this class of object.'''
        return '%s, %s' % (self.mRNA.name, self.num)

    class Meta:
        verbose_name_plural = 'CDS Regions'

    def length(self):
        return self.end_position - self.start_position + 1

class GeneSymbolManager(models.Manager):
    def gene_symbols_no_flybase_ID(self):
        symbols_without_flybase_ID = []

        all_symbols = self.all()
        print('Num symbols: ',len(all_symbols))
        for i,symbol in enumerate(all_symbols):
            if (i % 10000 == 0):
                print('Processing: ',i)
            flybase_id = symbol.flybase_ID()
            if flybase_id is None:
               symbols_without_flybase_ID.append(symbol.symbol)
        return symbols_without_flybase_ID

class GeneSymbol(models.Model):
    '''Data about a symbol representing a gene in different systems.'''
 
    symbol = models.CharField(max_length=255)
    translations = models.ManyToManyField('self')

    objects = GeneSymbolManager()

    def __str__(self):
        '''Define the string representation of this class of object.'''
        return self.symbol
  
    def all_symbols(self):
        '''Return a list of all translations of this gene symbol.'''
        return([self.symbol] + [t.symbol for t in self.translations.all()])

    def flybase_ID(self):
        all_translations = self.all_symbols()
        for trans in all_translations:
            if trans[:4] == 'FBgn':
                return trans
        return None

    @staticmethod
    def normalize(symbol):
        '''Return the normalized version of symbol.'''
    
        dpse_match = re.compile(r'dpse\\(.+)', flags=re.I).match
        ga_match = re.compile(r'ga(\d+)', flags=re.I).match
        cg_match = re.compile(r'cg(\d+)', flags=re.I).match
        fbgn_match = re.compile(r'fbgn(\d+)', flags=re.I).match
        gleanr_match = re.compile(r'gleanr_(\d+)', flags=re.I).match
        dpse_gleanr_match = re.compile(r'dpse_gleanr_(\d+)', flags=re.I).match
        normalized_symbol = symbol

        # The "Dpse\" prefix should be stripped.
        dpse_matched = dpse_match(normalized_symbol)
        if dpse_matched:
            normalized_symbol = dpse_matched.group(1)

        # "GA" symbols should be in the format: GAXXXXXX
        ga_matched = ga_match(normalized_symbol)
        if ga_matched:
            normalized_symbol = ''.join(('GA', ga_matched.group(1)))

        # "CG" symbols should be in the format: CGXXXXXX
        cg_matched = cg_match(normalized_symbol)
        if cg_matched:
            normalized_symbol = ''.join(('CG', cg_matched.group(1)))

        # "FlyBase ID" symbols should be in the format: FBgnXXXXXX
        fbgn_matched = fbgn_match(normalized_symbol)
        if fbgn_matched:
            normalized_symbol = ''.join(('FBgn', fbgn_matched.group(1)))

        # "GLEANR" symbols should be in the format: dpse_GLEANR_XXXXXX
        gleanr_matched = gleanr_match(normalized_symbol)
        dpse_gleanr_matched = dpse_gleanr_match(normalized_symbol)
        match = None
        if gleanr_matched:
            match = gleanr_matched
        if dpse_gleanr_matched:
            match = dpse_gleanr_matched
        if match:  
            normalized_symbol = ''.join(('dpse_GLEANR_', match.group(1)))

        return normalized_symbol


class GeneImportLog(ImportLog):
    '''Metadata about the import of a particular Gene object.'''
    gene_count = models.PositiveIntegerField()


class GeneSymbolImportLog(ImportLog):
    '''Metadata about the import of a set of GeneSymbol data.'''
    
    symbol_count = models.PositiveIntegerField()
    translation_count = models.PositiveIntegerField()
  
  
class GeneBatchProcess(BatchProcess):
    '''Metadata about the processing of a "batch gene" request.'''
    original_species = models.CharField(max_length=255)
    original_request = models.TextField()
    total_symbols = models.PositiveIntegerField(null=True)
    failed_symbols = models.PositiveIntegerField(null=True)

    @staticmethod
    def generate_unique_tag():
        '''Return a unique tag used for delivery of "batch gene" results.'''
        
        candidate = None
        while 1:
            # Candidates are currently strings of 32 random characters.
            # Loop through candidates until we find an unused one.
            # This should rarely continue past one iteration.
            candidate = ''.join(
              random.choice(string.ascii_uppercase + string.ascii_lowercase +\
                string.digits) for x in range(32))
            if os.path.exists(os.path.join(settings.PSEUDOBASE_DELIVERY_ROOT, 
              candidate)):
                # This means the directory already exists.
                continue

            for b in GeneBatchProcess.objects.filter(delivery_tag=candidate):
                # This means another process already has already generated
                # this tag, but no files exist for it yet.
                # It is highly unlikely for this to occur.
                continue
            break
        return candidate
