'''Models for the gene application.'''

import os
import random
import re
import string
import textwrap

from django.conf import settings
from django.db import models

from common.models import Strain, Chromosome, StrainManager
from common.models import BatchProcess, ImportLog

from chromosome.models import ChromosomeBase


# class GeneManager(models.Manager):
#     def ref_strain_gene_for_chrom_and_code(self,chrom_name,import_code):
#         ref_strain_gene = None
#         try:
#            rfg = self.filter(chromosome__name=chrom_name,import_code=import_code,)



class Gene(models.Model):
    '''Sequence Data and metadata about a particular gene sequence.'''
    
    strain = models.ForeignKey(Strain)
    chromosome = models.ForeignKey(Chromosome)
    start_position = models.PositiveIntegerField()
    end_position = models.PositiveIntegerField()
    import_code = models.CharField(max_length=255, db_index=True)
    strand = models.CharField(max_length=1)
    bases = models.TextField() #(editable=False)

    # objects = GeneManager()

    def __str__(self):
        '''Define the string representation of this class of object.'''
        return '%s, %s, %s, %s' % (self.chromosome.name, self.import_code, self.strain.name, self.strain.release.name)


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


    def max_bases_per_position(self,strains):
        # Used in post alignment

        #cds_list = self.largest_transcript().cds_list()

        bases_per_position = []
        for strain in strains:
            bases_per_position.append(self.largest_transcript().base_positions_for_strain(strain))

        bases_len = len(bases_per_position[0])
        max_bases_per_pos = []
        for j in range(bases_len):
             max_for_pos = 0
             for i in range(len(bases_per_position)):
                 bases = bases_per_position[i][j]
                 if len(bases) > max_for_pos:
                     max_for_pos = len(bases)
             max_bases_per_pos.append(max_for_pos)

        return max_bases_per_pos

    def fasta_header(self, delimiter='|',use_strain=None):
        '''Return a FASTA-compliant header containing sequence metadata.
        
        If delimiter is specified, it is used instead of the default.

        If use_strain is specified, use that strain to specify strain name etc (while using self, ie gene, to obtain
        sequence ranges). This is used because default sequence ranges for each gene are stored against the reference strain.
        An actual gene record is created for a non-ref strain only if the sequence range needs to be overridden for that strain.

        
        '''

        strain = self.strain if use_strain is None else use_strain

        largest_transcript = self.largest_transcript()
        return r'>%s' % delimiter.join((strain.species.name,
          strain.name,strain.release.name,
          '%s_%s %s' %(self.chromosome.name, self.start_position if largest_transcript is None else largest_transcript.start_position(), '' if largest_transcript is None else largest_transcript.name),
          self.symbols()))
  
    def fasta_bases(self, wrapped=True,use_strain=None, max_bases_per_pos = None):
        '''Return the sequence data for the specified range.
      
        This data is retrieved from the data file.  It is generally wrapped
        to 75 characters for format compliance.

        If use_strain is specified, use that strain to specify strain name etc (while using self, ie gene, to obtain
        sequence ranges). This is used because default sequence ranges for each gene are stored against the reference strain.
        An actual gene record is created for a non-ref strain only if the sequence range needs to be overridden for that strain.

        '''

        strain = self.strain if use_strain is None else use_strain

        largest_transcript = self.largest_transcript()
        if largest_transcript is None:
            bases = self.bases
        else:
            #ref_strain = Strain.objects.get(name__contains='refer',release__name__contain='3')
            # ref_strain = Strain.objects.ref_strain_for_release('r3.04')
            # if ref_strain is None:
            #     bases = self.bases
            # else:
            if max_bases_per_pos is None:
                bases = largest_transcript.bases_for_strain(strain)   #(self.strain)
            else: # use post alignment
                base_positions = largest_transcript.base_positions_for_strain(strain)
                bases_aligned = []
                for i, base in enumerate(base_positions):
                    if len(base_positions[i]) < max_bases_per_pos[i]:
                        if self.strand == '-':
                            base_aligned_str = ChromosomeBase.realign_char * (max_bases_per_pos[i] - len(base_positions[i])) + base_positions[i]
                        else:
                            base_aligned_str = base_positions[i] + ChromosomeBase.realign_char * (max_bases_per_pos[i] - len(base_positions[i]))
                        # bases_str += ChromosomeBase.realign_char * (max_bases[i] - len(bases[i]))
                        bases_aligned.append(base_aligned_str)
                    else:
                        bases_aligned.append(base_positions[i])

                bases = ''.join(bases_aligned)
                if self.strand == '-':
                    bases = MRNA.reverse_complement(bases)

    
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
    def multi_gene_fasta(symbol, species, show_aligned=False):
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


        #Old Method - check for original release (pse1) formatted genes
        # genes = Gene.objects.filter(strain__species__pk__in=species).filter(
        #   import_code__in=n_symbols, strain__release__name=settings.ORIGINAL_RELEASE_VERSION).order_by('-strain__is_reference',
        #     'strain__species__id', 'strain__name')
        # for g in genes:
        #     yield (g.fasta_header(), g.fasta_bases())


        #New method Flybase release r3.04 onwards
        all_strains = Strain.objects.strains_in_species_list(species,release_to_exclude=settings.ORIGINAL_RELEASE_VERSION)
        strains = []
        for strain in all_strains:
            try:
                genes = Gene.objects.filter(
                    import_code__in=n_symbols, strain__release__name=strain.release.name).order_by(
                    '-strain__is_reference',
                    'strain__species__id', 'strain__name')
                cb = ChromosomeBase.objects.get(strain=strain, chromosome=genes[0].chromosome)
                if cb.missing_data():
                    print('Missing chromosomebase data for strain: ',strain)
                else:
                    strains.append(strain)
            except:
                print('Missing chromosomebase record for strain: ',strain)
                pass # Only process strain if chromosomebase data actually exists


        #Pre-process to determine post-alignment
        alignment_strains = []
        for strain in strains:
            if strain.is_reference:
                try:
                    ref_gene = Gene.objects.get(strain=strain, import_code__in=n_symbols)
                    alignment_strains.append(strain)  # ref gene exists
                except:
                    pass
            else:
                strain_gene = None
                try:
                    strain_gene = Gene.objects.get(strain=strain, import_code__in=n_symbols)
                except:
                    pass
                if strain_gene is None:
                    ref_strain = Strain.objects.ref_strain_for_release(strain.release.name)
                    try:
                        ref_gene = Gene.objects.get(strain=ref_strain, import_code__in=n_symbols)
                        alignment_strains.append(strain) # Strain uses ref gene base positions, and ref gene exists
                    except:
                        pass
        if len(alignment_strains) < 2 or (not show_aligned):
            pass
        else:
            for alignment_strain in alignment_strains:
                strains.remove(alignment_strain)
            max_bases_per_pos = ref_gene.max_bases_per_position(alignment_strains)
            for alignment_strain in alignment_strains:
                yield (ref_gene.fasta_header(use_strain=alignment_strain), ref_gene.fasta_bases(use_strain=alignment_strain, max_bases_per_pos = max_bases_per_pos))

        for strain in strains: # Remaining strains which don't use ref gene base positions
            strain_gene = None
            try:
              strain_gene = Gene.objects.get(strain=strain,import_code__in=n_symbols)
            except:
                pass

            if strain_gene is None:
                ref_strain = Strain.objects.ref_strain_for_release(strain.release.name)
                try:
                    ref_gene = Gene.objects.get(strain=ref_strain, import_code__in=n_symbols)
                    yield (ref_gene.fasta_header(use_strain=strain), ref_gene.fasta_bases(use_strain=strain))
                except:
                    pass
            else:
                yield (strain_gene.fasta_header(), strain_gene.fasta_bases())



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

    @staticmethod
    def reverse_complement(bases):
        compl = {'A':'T','C':'G','G':'C','T':'A','-':'-'}
        rev_bases = ''
        for base in reversed(bases):
            if base in compl:
                rev_bases += compl[base]
            else:
                rev_bases += base

        return rev_bases


    def bases_for_strain(self,strain):
        bases_list = []
        try:
            cb = ChromosomeBase.objects.get(strain=strain,chromosome=self.gene.chromosome)
            if cb.missing_data():
                print('Missing chromosome base data for strain: ',strain, ' chromosome: ',self.gene.chromosome)
                return ''
        except:
            print('Missing chromosome bases for strain: ',strain, ' chromosome: ',self.gene.chromosome)
            return ''

        for cds_range in self.cds_list():
            cds_bases = cb.fasta_bases(cds_range[0],cds_range[1])
            bases_list.extend(cds_bases)
            bases = ''.join(bases_list)

        if self.gene.strand == '-':
            return MRNA.reverse_complement(bases)
        else:
            return bases

    def base_positions_for_strain(self,strain):

        strain_bases_per_position = []
        try:
             cb = ChromosomeBase.objects.get(strain=strain, chromosome=self.gene.chromosome)
             if cb.missing_data():
                print('Missing chromosome base data for strain: ',strain, ' chromosome: ',self.gene.chromosome)
                return strain_bases_per_position
        except:
            print('Missing chromosome bases for strain: ',strain, ' chromosome: ',self.gene.chromosome)
            return strain_bases_per_position


        for cds_range in self.cds_list():
            strain_bases_per_position.extend(cb.get_bases_per_position(cds_range[0], cds_range[1]))
        return strain_bases_per_position

    def start_position(self):
        cds_list = self.cds_list()

        if len(cds_list) == 0:
            return -1

        if self.gene.strand == '-':
           return cds_list[-1][-1]
        else:
           return cds_list[0][0]


    def end_position(self):
        cds_list = self.cds_list()

        if len(cds_list) == 0:
            return -1
        if self.gene.strand == '-':
            return cds_list[0][0]
        else:
            return cds_list[-1][-1]


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

    def __str__(self):
        '''Define the string representation of this class of object.'''
        return 'Imported: %s File Path: %s' % (str(self.end), self.file_path)


class GeneSymbolImportLog(ImportLog):
    '''Metadata about the import of a set of GeneSymbol data.'''
    
    symbol_count = models.PositiveIntegerField()
    translation_count = models.PositiveIntegerField()
  
    def __str__(self):
        '''Define the string representation of this class of object.'''
        return 'Imported: %s File Path: %s'  % (str(self.end), self.file_path)

class GeneBatchProcess(BatchProcess):
    '''Metadata about the processing of a "batch gene" request.'''
    original_species = models.CharField(max_length=255)
    original_request = models.TextField()
    total_symbols = models.PositiveIntegerField(null=True)
    failed_symbols = models.PositiveIntegerField(null=True)

    def __str__(self):
        '''Define the string representation of this class of object.'''
        return '%s, %s, %s' % (self.submitted_at,self.submitter_email,self.batch_status)

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
