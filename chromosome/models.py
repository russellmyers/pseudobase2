'''Models for the chromosome application.'''

import array
import base64
import os
import random
import re
import string
import struct
import textwrap
import sys
from os.path import join
import gzip
import json

from django.conf import settings
from django.db import models
import django.utils.timezone
from django.db import connection, transaction
from django.db.models import Q

from chromosome.utils import VCFRecord
from django.core.cache import get_cache
import hashlib


from common.models import Strain, StrainSymbol,Chromosome, ImportLog, ImportFileReader, BatchProcess

@transaction.autocommit
def update_import_log_outside_transaction(importlogrec):
    importlogrec.save()    
    

def my_custom_sql(import_id):
    from django.db import connection, transaction
    with connection.cursor() as cursor:
        cursor.execute("UPDATE chromosome_chromosomebatchimportlog SET records_read = 42 WHERE id = %s", [import_id])


def hashfile(path, blocksize = 65536):
    afile = open(path, 'rb')
    hasher = hashlib.md5()
    buf = afile.read(blocksize)
    while len(buf) > 0:
        hasher.update(buf)
        buf = afile.read(blocksize)
    afile.close()
    return hasher.hexdigest()



class ChromosomeBaseManager(models.Manager):
    def get_all_ref_bases(self,chrom_name, flybase_release_name):
        try:
            strain_name = StrainSymbol.objects.filter(strain__is_reference=True, strain__release__name=flybase_release_name)[0].strain.name
            chrom = self.filter(strain__name=strain_name,strain__release__name=flybase_release_name, chromosome__name=chrom_name)[0]
            return chrom.get_all_bases()
        except:
            return None


class ChromosomeBase(models.Model):
    '''Sequence Data and metadata about a particular chromosome.'''
    
    strain = models.ForeignKey(Strain)
    chromosome = models.ForeignKey(Chromosome)
    start_position = models.PositiveIntegerField()
    end_position = models.PositiveIntegerField()
    file_tag = models.CharField(max_length=32)

    pad_char = 'N' #For unknown bases outside bounds of self.start_position, self.end_position
    realign_char = '-'  # where insertions occur in a strain, re-align other strains padded with this char

    objects = ChromosomeBaseManager()

    ordering = ('chromosome','strain',)

    def __str__(self):
        '''Define the string representation of this class of object.'''
        rel = 'Norel' if self.strain.release is None else self.strain.release.name
        return '%s %s %s' % (rel, self.chromosome, self.strain.name)


  
    def has_insertions(self,stAbs,endAbs):
        #check if selected region has inserts, ie at least one position with > 1 base
        #Note: returns false if selected region is out of bounds
        
        if (endAbs < self.start_position):
            return False
        if (stAbs > self.end_position):
            return False
        
        start = self._position_offset(stAbs)
        end = self._position_offset(endAbs)
        
        if (stAbs < self.start_position):
            start = self._position_offset(self.start_position)
        if (endAbs >= self.end_position):
            end = self._position_offset(self.end_position - 1)
            
        
        #pdb.set_trace()
        #f = open(self.data_file_path) rbm 9/4/19 doesn't seem to be needed
    
        try:
            start_offset = self._get_byte_offset_from_index(start)
                # The end position is incremented by 1 because users expect the
            # results to be inclusive.
            end_offset = self._get_byte_offset_from_index(end + 1) 
            if end_offset is None:
                return False
            
            seq_num_bytes = end_offset - start_offset
            
            if (seq_num_bytes == end + 1 - start):
                return False
            else:
                return True
            
  
        finally:
            #f.close()  rbm 9/4/19
            pass
    
        return False



    def _position_offset(self, position):
        '''Return position as offset by the start_position.
        
        Not all sequences start a position 1; thus, the start_position of any
        particular sequence is unknown.  The sequence data, however, always
        starts at byte 0 of the data file.  For this reason, we must make sure
        to offset position such that they get the actual requested position.
        
        For example:
        
        A sequence has a start_position of 159.
        A user requests position 159 of that sequence.
        If we retrieved the data indexed at position 159 of the data file, we
        would actually be retrieving position 317, which would be incorrect.
        
        '''
        
        return (position - self.start_position)
 
    def _get_byte_offset_ranges_from_index(self, start,end):
        '''Look up byte offsets of data in position start - end (inclusive) from the index.
        
        Note: The index file keeps track of the number of bytes from the start of
        the data file where any particular position begins.
        
        '''
    
        format = 'I'
        format_size = struct.calcsize(format)

        f = open(self.index_file_path,'rb')

        try:
            f.seek(start * format_size)
            data = f.read(format_size * (end + 1 - start))
        finally:
            f.close()
      
        if not data:
            # This happens if we request a position that doesn't exist.
            # Typically, this is only seen when requesting a position that is
            # after the end of the data file.
            return None
        else:
            
            data_list = [data[i:i+format_size] for i in range(0, len(data), format_size)]
            unpacked = []
            for d in data_list:
                unpacked.append(struct.unpack(format, d)[0])
                
            return unpacked   
    
    def _get_byte_offset_from_index(self, n):
        '''Look up the byte offset of the data in position n from the index.
        
        The index file keeps track of the number of bytes from the start of
        the data file where any particular position begins.
        
        '''
    
        format = 'I'
        format_size = struct.calcsize(format)

        f = open(self.index_file_path,'rb')

        try:
            f.seek(n * format_size)
            data = f.read(format_size)
        finally:
            f.close()
      
        if not data:
            # This happens if we request a position that doesn't exist.
            # Typically, this is only seen when requesting a position that is
            # after the end of the data file.
            return None
        else:
            return struct.unpack(format, data)[0]

    def _base_data(self, start, end):
        '''Return a range of data from the data file, based on start and end.
        
        The ranged defined by start and end should be the real positions in
        the sequence that are desired.  All offsetting and coercion of the
        range definitions are done internally.
        
        '''
    
        f = open(self.data_file_path)
    
        try:
            start_offset = self._get_byte_offset_from_index(start)
            # The end position is incremented by 1 because users expect the
            # results to be inclusive.
            end_offset = self._get_byte_offset_from_index(end + 1) 
            data = None
      
            f.seek(start_offset)
            if end_offset is None:
                # Edge case where the last position requested is the last one
                # in the data file.  In that case, we read everything up until
                # the end of the file.
                data = f.read()
            else:
                # Most of the time, the position will be within the bounds of 
                # the data file.
                data = f.read(end_offset - start_offset)
        finally:
            f.close()
    
        return data
  
    def _get_data_file_path(self, postfix=''):
        '''Return the full filesystem path to the data file.
        
        If postfix is defined, it is appended to the path (this is used in the
        case of index and coverage files).
        
        '''
        
        return os.path.join(settings.PSEUDOBASE_CHROMOSOME_DATA_ROOT,
          '%s%s' % (self.file_tag, postfix))
    data_file_path = property(_get_data_file_path)

    def _get_index_file_path(self):
        '''Return the fule filesystem path to the index file.'''
        return self._get_data_file_path('.index')
    index_file_path = property(_get_index_file_path)
  
    def _get_coverage_file_path(self):
        '''Return the fule filesystem path to the coverage file.'''
        return self._get_data_file_path('.coverage')
    coverage_file_path = property(_get_coverage_file_path)
 
    def _get_total_bases(self):
        '''Return the total number of bases in this sequence.'''
        return self.end_position - self.start_position + 1
    total_bases = property(_get_total_bases)

    def valid_position(self, position):
        '''Check (naively) if position is logically possible.'''
        
        if position > self.end_position or position < self.start_position:
            return False
        return True

    def wrap_data(self,bases):
        
       try:
            eval('textwrap.TextWrapper(break_on_hyphens=False)')
            tw = textwrap.TextWrapper(width=75, 
                 break_on_hyphens=False)
       except TypeError:
            tw = textwrap.TextWrapper(width=75)
       return tw.wrap(bases)

    def clip(self,start_position,end_position):

        # clip seleced start and end positions to positions available for strain/chromosome in the database
        start_position_clipped = start_position if start_position >= self.start_position  else self.start_position
        end_position_clipped   = end_position   if end_position <= self.end_position else self.end_position
        
        return start_position_clipped,end_position_clipped

        
  
    def fasta_header(self, start_position, end_position, delimiter='|'):
        '''Return a FASTA-compliant header containing sequence metadata.
        
        If delimiter is specified, it is used instead of the default.
        
        '''
        rel = 'Norel' if self.strain.release is None else self.strain.release.name
        return r'>%s' % delimiter.join((self.strain.species.name,
          self.strain.name, self.chromosome.name,rel,
          '%s..%s' % (start_position, end_position)))

    def get_all_bases(self):
        bases = self._base_data(self.start_position-1, self.end_position)
        return bases

  
    def fasta_bases(self, start_position, end_position, wrapped=True):
        '''Return the sequence data for the specified range.
        
        This data is retrieved from the data file.  It is generally wrapped
        to 75 characters for format compliance.
        
        '''
        if start_position > self.end_position:
           return self.wrap_data('No data beyond base %s available for this strain' % (str(self.end_position)))
 

        error_data = []
        
        start_position_clipped,end_position_clipped = self.clip(start_position,end_position)
        
        if not self.valid_position(start_position):
            #error_data.append(
            #  'Invalid start position (%s); must be at least %s.' % \
            #    (start_position, self.start_position))
            pass
        if not self.valid_position(end_position):
            #error_data.append(
            #  'Invalid end position (%s); must be no more than %s.' % \
            #   (end_position, self.end_position))
            pass

        if error_data:
            return error_data
        else:
            start = self._position_offset(start_position)
            end = self._position_offset(end_position)
            if self.outside_bounds(start_position,end_position):
                bases = self.pad(start_position,end_position + 1)
            else:    
                bases = self._base_data(self._position_offset(start_position_clipped),
                  self._position_offset(end_position_clipped))
                bases = self.pad(start_position,start_position_clipped) \
                        + bases  \
                        + self.pad(end_position_clipped,end_position)
      
            if wrapped:
                # We have to go through this little eval dance because the
                # "break_on_hyphens" keyword arg only exists in python 2.6+.
                return self.wrap_data(bases)
#                try:
#                    eval('textwrap.TextWrapper(break_on_hyphens=False)')
#                    tw = textwrap.TextWrapper(width=75, 
#                      break_on_hyphens=False)
#                except TypeError:
#                    tw = textwrap.TextWrapper(width=75)
#                return tw.wrap(bases)
            else:
                return bases

    def fasta_bases_formatted(self, start_position, end_position, max_bases=None,wrapped=True):
        #re-Formatted version of fasta bases - cater for aligning insertions
        
        if start_position > self.end_position:
           return self.wrap_data('No data beyond base %s available for this strain' % (str(self.end_position)))
        
        bases = self.get_bases_per_position(start_position,end_position)
        
        #bases_str = ''
        bases_aligned = []
        for i,base in enumerate(bases):

            #bases_str += bases[i]
            if (max_bases):
                if len(bases[i]) < max_bases[i]:
                   base_aligned_str = base + ChromosomeBase.realign_char * (max_bases[i] - len(bases[i]))
                   #bases_str += ChromosomeBase.realign_char * (max_bases[i] - len(bases[i]))
                   bases_aligned.append(base_aligned_str)
                else:
                   bases_aligned.append(base)

            else:
                bases_aligned.append(base)


        bases_str = ''.join(bases_aligned)
        if wrapped:
            return self.wrap_data(bases_str)
        else:
            return bases_str


    def get_bases_per_position(self,start_position,end_position):
        #Get bases at each position (some positions have multiple bases, ie insertions)
 
        if hasattr(self, 'cached_bases_data'):
            print('Has cached bases')
            if  (self.cached_bases_data['start_position'] == start_position 
                 and  self.cached_bases_data['end_position'] == end_position):
                 print ('...and cache matches!')
                 bases = self.cached_bases_data['bases']
                 return bases
           
        else:
            print ('!!!!!!!No cached bases')
          
        if self.outside_bounds(start_position,end_position):
            bases = self.pad(start_position,end_position + 1)
            return bases
        
        start_position_clipped,end_position_clipped = self.clip(start_position,end_position)

        bases = ['N' for i in range(start_position,start_position_clipped)]
      
        if  (self.has_insertions(start_position,end_position)):
            bases_str_in_clipped_range = self._base_data(self._position_offset(start_position_clipped),
                  self._position_offset(end_position_clipped))
            offsets = self._get_byte_offset_ranges_from_index(self._position_offset(start_position_clipped),self._position_offset(end_position_clipped))
            st_offset = offsets[0]
            bases_list_in_clipped_range = []
            for i,off in enumerate(offsets):
                if (i < len(offsets)-1):
                    bases_list_in_clipped_range.append(bases_str_in_clipped_range[off - st_offset: offsets[i+1] - st_offset])
                else:
                    bases_list_in_clipped_range.append(bases_str_in_clipped_range[off - st_offset:])
                
            bases.extend(bases_list_in_clipped_range)
#            for i in range(start_position_clipped,end_position_clipped + 1):
#                bases_this_pos = self._base_data(self._position_offset(i),self._position_offset(i))
#                if (bases_this_pos):
#                    bases.append(bases_this_pos)
#                else:
#                    bases.append('X')
        else:
                base_data = self._base_data(self._position_offset(start_position_clipped),self._position_offset(end_position_clipped))
                bases.extend(list(base_data))             

        bases.extend(['N' for i in range(end_position_clipped+1,end_position+1)])    
         
        self.cached_bases_data = {'start_position':start_position,'end_position':end_position,'bases':bases}
        return bases

    def pad(self,base_from,base_to):
        pad = ChromosomeBase.pad_char * (base_to - base_from)
        return pad
    
    def outside_bounds(self,start_position,end_position):
        #Check if requested start/end range is completely outside bounds
        # eg requested positions 01..100 and chromsome start pos is 120
        # or requested positions 1000000..1100000 and chromsome end pos is 900000
        
        if (start_position > self.end_position) or (end_position < self.start_position):
            return True
        
        return False

    @staticmethod
    def max_num_bases_per_position(bases_per_position):
        # could be done with numpy much easier/quicker
        
        max_bases = []
        if (len(bases_per_position) == 0):
            return max_bases
        
        for j in range(0,len(bases_per_position[0])):
            max_num = 0
            for i in range(0,len(bases_per_position)):
                if len(bases_per_position[i][j]) > max_num:
                    max_num = len(bases_per_position[i][j])
            max_bases.append(max_num)        
        return max_bases         
 
    @staticmethod  
    def multi_strain_fasta(chromosome, species, start, end, show_aligned=False):
        '''Generator which returns FASTA header/data individually.
        
        There can potentially be a lot of sequences for any given pair of
        chromosome and species.  We return a generator so that we don't have
        to store all those sequences (which can be large even individually) in
        memory for any longer than necessary.
        
        This method primarily handles the "search by chromosome" functionality
        from the web interface.
        
        '''
        
        chromosomes = ChromosomeBase.objects.filter(
          chromosome=chromosome).filter(strain__species__in=species).order_by(
            '-strain__is_reference', 'strain__species__id', 'strain__name')

        bases_per_position = []
        max_bases = None
        if (len(chromosomes) < 2) or (not show_aligned):
            pass
        else:
            for c in chromosomes:
                bases_per_position.append(c.get_bases_per_position(start, end))
            max_bases = ChromosomeBase.max_num_bases_per_position(bases_per_position)
    
        for c in chromosomes:
            if (len(chromosomes) < 2) or (not show_aligned):
                yield (c.fasta_header(start, end), c.fasta_bases(start, end))
            else:
                yield (c.fasta_header(start, end), c.fasta_bases_formatted(start, end,max_bases))
  
    @staticmethod
    def generate_file_tag():
        '''Return a unique file tag.
        
        A file tag is a random string of characters used as a unique value for
        any given ChromosomeBase object's data, index and coverage files.
        
        '''
        
        candidate = None
        while 1:
            # Candidates are currently strings of 32 random characters.
            # Loop through candidates until we find an unused one.
            # This should rarely continue past one iteration.
            candidate = ''.join(random.choice(string.ascii_uppercase + \
              string.ascii_lowercase + string.digits) for x in range(32))

            if os.path.exists(os.path.join(
              settings.PSEUDOBASE_CHROMOSOME_DATA_ROOT, candidate)):
                # This means the file already exists.
                continue

            for b in ChromosomeBase.objects.filter(file_tag=candidate):
                # This means another process already has already generated
                # this file tag, but no files exist for it yet.
                # It is highly unlikely for this to occur.
                continue
            
            break
        return candidate
  
    class Meta:
        '''Define Django-specific metadata.'''
        #ordering = ('strain__species__pk', 'chromosome__name', 'strain__name')
        ordering = ('strain__release__name','chromosome__name','-strain__is_reference','strain__name')


# Deprecated - now uses ChromosomeBatchImportLog
class ChromosomeImportLog(ImportLog):
    '''Metadata about the import of a particular ChromosomeBase object.'''
    
    base_count = models.PositiveIntegerField()
    clip_count = models.PositiveIntegerField()

    def __str__(self):
        '''Define the string representation of this class of object.'''
        return 'Imported: %s File Path: %s'  % (str(self.end), self.file_path)



class ChromosomeBatchImportProcessManager(models.Manager):
    def current_batches(self):
        #Pending or Active
        return self.filter(Q(batch_status='P') | Q(batch_status='A'))  
    
    def pending_batches(self):
        #Pending
        return self.filter(Q(batch_status='P'))
 
    def running_batches(self):
        #Active
        return self.filter(Q(batch_status='A'))
    
    def latest_finished_batch(self):
        #Last batch to finish (whether it completed successfully or failed)
        return self.latest('id')
        
    

class ChromosomeBatchImportProcess(BatchProcess):
    original_request = models.TextField()
    
    objects = ChromosomeBatchImportProcessManager()

    def __str__(self):
        '''Define the string representation of this class of object.'''
        return 'Submitted: %s Status: %s' % (self.submitted_at, self.batch_status)

    def num_files_in_batch(self):
        batchimports = self.chromosomebatchimportlog_set.all()  #ChromosomeBatchImportLog.objects.filter(batch=self.id)
        return len(batchimports)


    
    def set_orig_request_from_filenames(self,filenames):
        #pending_import_rel_path = 'raw_data/chromosome/pending_import/'
        rel_paths = [os.path.join(settings.PSEUDOBASE_CHROMOSOME_RAW_DATA_PENDING_PREFIX,filename) for filename in filenames]
        self.set_orig_request_from_relpaths(rel_paths)
    
    def set_orig_request_from_relpaths(self,rel_paths):
        orig_req = ''
        for i,rel_path in enumerate(rel_paths):
            file_path = os.path.abspath(rel_path)
            orig_req += file_path
            if i == len(rel_paths) - 1:
                pass
            else:
                orig_req += '\n'
        self.original_request = orig_req   
        
    
    @staticmethod
    def create_batch_and_import_file(chromosome_data,flybase_release  = ' ',ref_chrom=None):
        #helper static method to create a batch and import single file within it
        #chromosome_data contains relative path eg ./raw_data/chromosome/pending_import/file.txt
        
        transaction.commit_unless_managed()
        transaction.enter_transaction_management()
        transaction.managed(True)
        try:
               
            current_batches = ChromosomeBatchImportProcess.objects.current_batches() #ChromosomeBatchImportProcess.objects.filter(Q(batch_status='P') | Q(batch_status='I'))   
            if (len(current_batches) > 0):
               raise Exception('Batch import already in process. Please wait ')
            
            bp = ChromosomeBatchImportProcess(submitted_at = django.utils.timezone.now(),batch_status = 'P')
            
#            orig_req = ''
#            abs_path = os.path.abspath(chromosome_data)
#            orig_req += abs_path
#
#            bp.original_request = orig_req  
            bp.set_orig_request_from_relpaths([chromosome_data])
            
            bp.save()
           
            
            bp.start()
            bp.save()
            chr_importer = ChromosomeImporter(chromosome_data,flybase_release=flybase_release, ref_chrom = ref_chrom)
            chr_importer.import_data(bp)
            chr_importer.print_summary()
            bp.stop()
            bp.save()

            transaction.commit()
            transaction.leave_transaction_management()
            connection.close()
            return bp
 
        except Exception as e:
            transaction.rollback()
            transaction.leave_transaction_management()
            raise Exception('Import failed: ' + str(e))   
            return None
    

# Import log for files imported via batch process
class ChromosomeBatchImportLog(ImportLog):

    base_count = models.PositiveIntegerField(null=True,blank=True)
    clip_count = models.PositiveIntegerField(null=True,blank=True)
    batch = models.ForeignKey(ChromosomeBatchImportProcess)
    status = models.CharField(max_length=1, db_index=True, default='P')
    records_read = models.PositiveIntegerField(blank=True,default=0)
    chromebase = models.ForeignKey(ChromosomeBase,null=True,blank=True)
    vcf_meta_data = models.TextField(null=True,blank=True)

    def __str__(self):
        '''Define the string representation of this class of object.'''
        return 'Status: %s Base Count: %s Imported: %s' % (self.status, self.base_count, str(self.end))

    
class ChromosomeImportFileReader(ImportFileReader):
    # Not a database table
    def __init__(self,fPath,target_field_names=None):
           if target_field_names is None:
              target_field_names = ['chromosome_name', 'strain_name', 'position', 
                                     'coverage', 'base'] 
           super(ChromosomeImportFileReader, self).__init__(fPath,target_field_names)
    

    def _reference_format(self, line):
        '''Parse a line in "reference" format and return a list of the data.
      
        The "reference" format is 4 tab-delimited fields, each field containing
        a single value.
      
        NOTE: The coverage value here defaults to 1, as the reference data has
        no coverage information.
      
        '''
        
        return [line[0], line[1]+'_pse1', int(line[2]), 1, line[3].upper()]

    def _standard_format(self, line):
        '''Parse a line in "standard" format and return a list of the data.
      
        The "standard" format is 4 tab-delimited fields.  The third field
        contains three space-delimited values.  The first column is empty.
      
        '''
        #pdb.set_trace()
        replace_whitespace = re.compile(r'\s').sub
        base_info = line[3].split(' ', 2)
        return [str(line[1]), str(line[2]) + '_pse1', int(base_info[0]),
          base_info[1].upper(), replace_whitespace('', base_info[2]).upper()]
    
    def _determine_format_parser_from_example_line(self,example_line):
          if example_line is None:
              return None
    
          if len(example_line) == 4:
            if example_line[0]:
                # Reference data format
                return self._reference_format
            else:
                # Standard data format
                return self._standard_format
          else:
            # Invalid data format
               return None
           
            
    def is_reference_format(self):
          return self.format_parser == self._reference_format         

class ChromosomeVCFImportFileReader():
    # Not a database table
    # Assumes gzip format, so can't use .next() functionality as per ImportFileReader (therefore not subclassed from ImportFileReader)
    def __init__(self,fPath):
        self.fPath = fPath
        self.vcf_file = None
        self.chrom = None
        self.strain = None
        self.chromosomes = {} # List of chromosomes if VCF contains multiple chromosomes of a group
        self.summary_flag_dict = {}


    def open(self):
       self.vcf_file = gzip.open(self.fPath, 'r')

    def close(self):
        self.vcf_file.close()

    def  get_chrom_and_strain(self):

        self.open()

        for i, line in enumerate(self.vcf_file):

            if i > 10000:
                break # Give up. May not actually be a VCF file

            line = line.decode('utf-8').rstrip()
            if line[:1] == '#':
               if line[:6] == '#CHROM':
                head = line[1:].split('\t')
                self.strain = head[-1]
            else:
               self.chrom = line.split('\t')[0]
               break  #assume comment head line is before first record

        self.close()

        return self.chrom,self.strain

    def get_num_records(self,also_retrieve_chromosomes=False):

        rec_num = 0
        tot_summary_flags = [0 for i in range(len(VCFRecord.vcf_types))]

        def_cache = get_cache('default')
        hash_key = hashfile(self.fPath)

        hash_record = def_cache.get(hash_key)
        if hash_record is None:
            pass # No cached record found
        else:
            rec_num = hash_record['num_records']
            if also_retrieve_chromosomes:
                if ('summary_flags_dict' in hash_record) and ('chromosomes' in hash_record):
                    self.summary_flag_dict = hash_record['summary_flags_dict']
                    self.chromosomes = hash_record['chromosomes']
                    return rec_num
                else:
                    pass
            else:
                return rec_num


        vcf_file = gzip.open(self.fPath, 'r')
        for line in vcf_file:
            #i+=1
            if also_retrieve_chromosomes:
                line = line.decode('utf-8').rstrip()
                if line[:1] == '#':
                    pass
                else:
                    if rec_num  % 100000 == 0:
                        print('_get_file_info progress: ' + str(rec_num) + ' file name: ' + self.fPath)
                    rec_num += 1
                    chrom = line.split('\t')[0]
                    if chrom in self.chromosomes:
                        self.chromosomes[chrom] +=1
                    else:
                        self.chromosomes[chrom] = 1

                    v = VCFRecord(line)
                    record_summary_flags = v.summary_flags()
                    tot_summary_flags = [prev_tot + record_summary_flags[i] for i, prev_tot in enumerate(tot_summary_flags)]

        hash_record = {'num_records':rec_num}

        if also_retrieve_chromosomes:
            self.summary_flag_dict = VCFRecord.tot_summary_flags_to_meta_data(tot_summary_flags)
            hash_record['summary_flags_dict'] = self.summary_flag_dict
            hash_record['chromosomes'] = self.chromosomes

        def_cache.set(hash_key, hash_record,604800)

        vcf_file.close()

        return rec_num

class ChromosomeImporter():
#Not a database table

    def __init__(self,chromosome_data,flybase_release = ' ',ref_chrom=None):
            self.chromosome_data = chromosome_data
            self.ref_chrom = ref_chrom
            self.flybase_release = flybase_release

            self.chromosome_data_fpath,self.chromosome_data_fname = os.path.split(self.chromosome_data)
            
            self.char_search = re.compile(r'[^ACTGKYSRWMND]').search
            self.replace_whitespace = re.compile(r'\s').sub
            self.replace_no_data = re.compile (r'D').sub
    

 
    def _lookup_strain(self, strain):
        '''Load a Strain object for association by its "short name".
    
        First, translate the "short name" of the strain into the appropriate
        "full name".  Then, look up the "full name" to get the related object
        which we can then use for associations.
       ''' 
        
#        OLD NOTE: We could (should) do this programmatically if we added a table
#        that mapped common strain notation to the appropriate Strain object.
#        It isn't necessary during the time crunch (a.k.a. now), but it should
#        probably be done if the translation table ends up changing often.
#    
#        
#        NEW NOTE: DONE! Below hard coded strain_translation is now replaced with StrainSymbol table:        
        
#    
#        STRAIN_TRANSLATION = {
#          'AFC12':     'American Fork Canyon, UT 12',
#          'FLG14':     'Flagstaff, AZ 14',
#          'FLG16':     'Flagstaff, AZ 16',
#          'FLG18':     'Flagstaff, AZ 18',
#          'MATHER32':  'Mather, CA 32',
#          'MATHERTL':  'Mather, CA TL',
#          'MV2-25':    'Mesa Verde, CO 2-25 reference line',
#          'MSH9':      'Mount St. Helena, CA 9',
#          'MSH24':     'Mount St. Helena, CA 24',
#          'PP1134':    'San Antonio, NM, Pikes Peak 1134',
#          'BDAPP1134': 'San Antonio, NM, Pikes Peak 1134',
#          'PP1137':    'San Antonio, NM, Pikes Peak 1137',
#          'BDAPP1137': 'San Antonio, NM, Pikes Peak 1137',
#          'BOGNUZ':    'El Recreo white mutant line',
#          'BOGERW':    'El Recreo white mutant line',
#          'ERW':       'El Recreo white mutant line',
#          'BOGTORO':   'Torobarroso',
#          'TORO':      'Torobarroso',
#          'MSH1993':   'Mount St. Helena, CA 1993',
#          'MSH39':     'Mount St. Helena, CA 39',
#          'SCI_SR':    'Santa Cruz Island',
#          'SCI':       'Santa Cruz Island',
#          'MSH22':     'Mount St. Helena, CA 22',
#          'SP138':     'SP138',
#          'MAO':       'MAO',
#          'ARIZ':      'Lowei',
#        }
#    
#        if strain.upper() in STRAIN_TRANSLATION:
#            lookup_strain = STRAIN_TRANSLATION[strain.upper()]
    
        try:
            s = StrainSymbol.objects.get(symbol=strain.upper()).strain
            return (s, False)
        except Strain.DoesNotExist:
            raise
  
    def _lookup_chromosome(self, chromosome):
        '''Load a Chromosome object for association by its name.'''
        chr_split = chromosome.split('_')
        if len(chr_split) > 1: # chromsome group, eg XL_group3b
           chr_split[1] = chr_split[1].lower()
           chr = '_'.join(chr_split)
        else:
           chr = chromosome
        return (Chromosome.objects.get(name=chr), False)
  
    def _coverage_index(self, n):
        '''Pack n into a byte for use in the coverage index.'''
        return struct.pack('B', n)
  
    def _index(self, n):
        '''Pack n into an integer for use in the base index.'''
        return struct.pack('I', n)


    def get_info(self,incl_rec_count = False,incl_all_chromosomes=False):

            chromosome_reader = None

            if self.chromosome_data.split('.')[-1] == 'gz':
                file_size = os.path.getsize(self.chromosome_data)
                if len(self.chromosome_data.split('.')) > 1 and (self.chromosome_data.split('.')[-2] == 'fasta'):
                    return {'file_name': self.chromosome_data_fname, 'file_size': file_size / 1000000.0,
                            'format': 'VCF gzipped', 'chromosome_name': 'Unknown', 'strain_name': 'Unknown','bases_count':0,'rec_count':0}
                else:
                    vcf_reader = ChromosomeVCFImportFileReader(self.chromosome_data)
                    chrom,strain_symbol = vcf_reader.get_chrom_and_strain()

                    release_name = ' '
                    if strain_symbol is None:
                        pass
                    else:
                        try:
                            str_sym = StrainSymbol.objects.get(symbol=strain_symbol)
                            release_name = str_sym.strain.release.name
                        except:
                            pass

                    rec_count = 0
                    bases_count = 0

                    chromosome_names = {}
                    summary_flag_dict = {}
                    num_chromosomes = 0

                    if incl_rec_count:
                        rec_count = vcf_reader.get_num_records(also_retrieve_chromosomes=incl_all_chromosomes)
                        if incl_all_chromosomes:
                            chromosome_names = vcf_reader.chromosomes
                            summary_flag_dict = vcf_reader.summary_flag_dict
                        ref_bases = ChromosomeBase.objects.get_all_ref_bases(chrom, release_name) #self.flybase_release)
                        if ref_bases is None:
                            print('No reference sequence imported for: ',chrom, release_name,' - Need to import ref fasta first')
                            bases_count = 0
                        else:
                            bases_count = len(ref_bases)
                    if chrom is None or strain_symbol is None:
                        return {'file_name': self.chromosome_data_fname, 'file_size': file_size / 1000000.0,
                            'format': 'Unknown','rec_count':rec_count, 'bases_count':bases_count}
                    else:
                        return {'file_name': self.chromosome_data_fname, 'file_size': file_size / 1000000.0,
                            'format': 'VCF gzipped','chromosome_name':chrom,'strain_name':strain_symbol,'rec_count':rec_count, 'bases_count':bases_count,'chromosome_names':chromosome_names,'num_chromosomes':len(chromosome_names),'summary_flag_dict':summary_flag_dict}




            try:
                chromosome_reader = ChromosomeImportFileReader(self.chromosome_data)
     
                if not chromosome_reader.format_parser:
                   file_size = os.path.getsize(self.chromosome_data)
                   return {'file_name':self.chromosome_data_fname,'file_size':file_size /1000000.0,'format':'unknown'}
                   #raise Exception('Unknown data format!')
                else:
                   # Get the data we only want to think about once.
                    first_data = chromosome_reader.get_and_parse_next_line(reset=True)

                    if incl_rec_count:
                        
                        rec_count = chromosome_reader.get_num_records()
                        first_data['rec_count'] = rec_count
                        
                    file_size = os.path.getsize(self.chromosome_data) 
                    first_data['file_size'] = file_size / 1000000.0
                    
                    if (chromosome_reader.is_reference_format()):
                        first_data['format'] = 'Reference'
                    else:
                        first_data['format'] = 'Non-ref'
                        
                    first_data['file_name'] = self.chromosome_data_fname
                    
                    first_data['exists_in_db'] = self.already_exists(first_data['strain_name'],first_data['chromosome_name'])
                    
                    
                    return  first_data
             
            except Exception as error:
                print ('whoops exc: ')
                print(error)
                raise
                
            finally:
                if (chromosome_reader):
                   chromosome_reader.finalise()
               
        
    def already_exists(self,strain_name,chromosome_name):
        try:
            strain = self._lookup_strain(strain_name)[0]
            chromosome = self._lookup_chromosome(chromosome_name)[0]
        except:
            return False

        #Check if chromosome/strain already exists
        if ChromosomeBase.objects.filter(chromosome = chromosome, strain = strain).exists():
            return True
        else:
           return False  


    def process_import_lines_vcf(self,chrom,strain):

        max_position = bases_total = 0

        new_bases_total = new_max_position = 0

        del_inds = {}

        poss_del_overlaps = []

        # Now process all the lines in the file (reset to get back to start)
        # data = chromosome_reader.get_and_parse_next_line(reset=True)

        #ref_bases, chrom_len, header = self.get_ref_seq_from_fasta(chrom,debug=True)
        ref_bases = ChromosomeBase.objects.get_all_ref_bases(chrom, self.flybase_release)

        tot_summary_flags = [0 for i in range(len(VCFRecord.vcf_types))]

        vcf_reader = ChromosomeVCFImportFileReader(self.chromosome_data)
        vcf_reader.open()

        for i,line in enumerate(vcf_reader.vcf_file):
            line = line.decode('utf-8').rstrip()
            if line[:1] == '#':
                continue
            else:
                v = VCFRecord(line)
                start_max_position = new_max_position
                start_bases_total = new_bases_total
                summary_flags = v.summary_flags()
                tot_summary_flags = [prev_tot + summary_flags[i] for i, prev_tot in enumerate(tot_summary_flags)]

                for n,base in enumerate(ref_bases[start_max_position:int(v.POS)-1]):
                   if (start_max_position + n) in del_inds:
                       new_bases_total, new_max_position = self.process_base_position('D', new_bases_total,
                                                                                      new_max_position, coverage=del_inds[start_max_position + n])
                       del del_inds[start_max_position + n]
                   else:
                        new_bases_total,new_max_position = self.process_base_position(base, new_bases_total, new_max_position)
                # Now - write current vcf line if called base (or write N if uncalled)
                if int(v.POS) - 1 in del_inds:
                    poss_del_overlaps.append([v.POS,del_inds])
                    #print('Pos delete overlap: ',v.POS,del_inds)
                    continue
                var_type,called_bases,read_depth = v.var_type()
                if  not v.passed_filter() or (var_type == 'U'):
                    new_bases_total,new_max_position = self.process_base_position('N', new_bases_total, new_max_position,coverage=0)
                else:
                    if var_type == '*':
                        pass
                    elif var_type == 'R': #Homo ref, or het called ref
                        new_bases_total, new_max_position = self.process_base_position(called_bases, new_bases_total,
                                                                                       new_max_position, coverage=read_depth)
                    else:
                         if var_type == 'S':
                             new_bases_total, new_max_position = self.process_base_position(called_bases,
                                                                                            new_bases_total,
                                                                                            new_max_position,
                                                                                            coverage=read_depth)
                         elif var_type == 'I':
                             new_bases_total, new_max_position = self.process_base_position(called_bases,
                                                                                            new_bases_total,
                                                                                            new_max_position,
                                                                                            coverage=read_depth)
                         elif var_type == 'D':
                             start_del_ind = new_max_position + 1
                             for i, base in enumerate(called_bases):
                                 ind_to_apply = start_del_ind + i
                                 del_inds[ind_to_apply] = read_depth


        print('Finished vcf. Now rest of ref. pos: ',new_max_position)
        start_max_position = new_max_position
        for n,base in enumerate(ref_bases[start_max_position:]):
            if (start_max_position + n) in del_inds:
                new_bases_total, new_max_position = self.process_base_position('D', new_bases_total,
                                                                               new_max_position, coverage=del_inds[start_max_position + n])
                del del_inds[start_max_position + n]
            else:
                new_bases_total,new_max_position = self.process_base_position(base, new_bases_total, new_max_position)


          #Now write any remaining bases to end of ref bases

        vcf_reader.close()

        vcf_meta_data = VCFRecord.tot_summary_flags_to_meta_data(tot_summary_flags)

        print('Num poss del overlaps ',len(poss_del_overlaps))
        print('Sample of overlaps: ')
        if len(poss_del_overlaps) >= 5:
            print(poss_del_overlaps[:5])
        else:
            print(poss_del_overlaps[:len(poss_del_overlaps)])



        return new_max_position, vcf_meta_data


    def get_ref_seq_from_fasta(self,chrom,debug=False):

        in_fasta = False

        chrom_len = 0

        fasta_seq = []

        header = ''

        fin = gzip.open(self.chromosome_data, 'r')
        for i, line in enumerate(fin):
            if i % 100000 == 0:
                if debug:
                    print('i: ' + str(i) + ' line: ' + line.decode('utf-8')[:150])

            line_str = line.decode('utf-8')
            if line_str[0] == '>':

                if debug:
                    print ('header: ' + str(i) + ' ' + line_str)

                if in_fasta:
                    return ''.join(fasta_seq), chrom_len,header

                if line_str[1:1 + len(chrom)] == chrom:
                    #fasta_seq.append(line_str.rstrip())
                    in_fasta = True
                    header = line_str.rstrip()
            else:
                if in_fasta:
                    fasta_line = line_str.rstrip()
                    fasta_seq.append(fasta_line)
                    chrom_len += len(fasta_line)

        return ''.join(fasta_seq), chrom_len,header


    def process_base_position(self, base, bases_total, max_position,coverage=0):

        i = max_position

        # A simple progress indicator, since processing can take a
        # while. Shows progress after every million records processed.
        if not i % (1000 * 1000):
            sys.stdout.write('.')
            sys.stdout.flush()

        if (i % (1000 * 100) == 0):
            print ('progres write: ', i)
            # log progress
            self.import_log.records_read = i
            # self.import_log.save()
            update_import_log_outside_transaction(self.import_log)
        ## Custom processing to handle data cleanup.


        # Check that the base string contains no invalid characters.
        if self.char_search(base):
            print \
                'Invalid character detected in base - line %s: %s' % \
                (i, base)
            return max_position + 1,bases_total+1
        else:

            # Change "D" characters in the base column to "-".
            base = self.replace_no_data(r'-', base)
            pass

        new_max_position = i + 1

        if coverage > 255:
           self.import_log.clip_count += 1
           coverage = 255


        ## Append the base and coverage data to the appropriate files.

        # Base data.
        base_string = base
        base_bytes = len(base_string)
        self.data_file.write(base_string)

        # Base data index.
        self.index_file.write(self._index(bases_total))
        new_bases_total = bases_total+base_bytes

        # Coverage data.
        self.coverage_file.write(self._coverage_index(coverage))

        return new_bases_total,new_max_position

    def process_import_lines_ref(self):

        max_position = bases_total = 0

        # Now process all the lines in the file (reset to get back to start)
        #data = chromosome_reader.get_and_parse_next_line(reset=True)

        ref_bases,chrom_len,header = self.get_ref_seq_from_fasta(self.ref_chrom,debug=True)

        n = 0

        #while data is not None:
        for i,base in enumerate(ref_bases):

            bases_total,max_position = self.process_base_position(base, bases_total, max_position)

        return max_position


    def process_import_lines_psepileup(self,chromosome_reader):

        max_position = bases_total = 0

        # Now process all the lines in the file (reset to get back to start)
        data = chromosome_reader.get_and_parse_next_line(reset=True)
        n = 0

        while data is not None:
            # Skip empty lines.
            if not data: continue

            # A simple progress indicator, since processing can take a
            # while. Shows progress after every million records processed.
            if not n % (1000 * 1000):
                sys.stdout.write('.')
                sys.stdout.flush()

            if (n % (1000 * 100) == 0):
                print ('progres write: ', n)
                # log progress
                self.import_log.records_read = n
                # self.import_log.save()
                update_import_log_outside_transaction(self.import_log)
            ## Custom processing to handle data cleanup.

            # Change "N" characters in the coverage column to 0.
            # Additionally change the value to be an integer instead of a
            # string.
            if data['coverage'] == 'N':
                data['coverage'] = 0

            # Coverages that are above 255 should be clipped to 255, so
            # that we don't need to store 2 bytes of data per coverage.
            data['coverage'] = int(data['coverage'])
            if data['coverage'] > 255:
                self.import_log.clip_count += 1
                data['coverage'] = 255

            # Check that the base string contains no invalid characters.
            if self.char_search(data['base']):
                print \
                    'Invalid character detected in base - line %s: %s' % \
                    (n, data['base'])
                break
            else:
                # Change "D" characters in the base column to "-".
                data['base'] = self.replace_no_data(r'-', data['base'])
                pass

            max_position = int(data['position'])

            ## Append the base and coverage data to the appropriate files.

            # Base data.
            base_string = ''.join(data['base'])
            base_bytes = len(base_string)
            self.data_file.write(base_string)

            # Base data index.
            self.index_file.write(self._index(bases_total))
            bases_total += base_bytes

            # Coverage data.
            self.coverage_file.write(self._coverage_index(data['coverage']))

            data = chromosome_reader.get_and_parse_next_line()
            n += 1

        return max_position

    def import_data(self,batch=None):
        
            #import pdb
            
            #pdb.set_trace()
            # Create a new ImportLog object to store metadata about the import.
            if (batch is None):
                self.import_log = ChromosomeImportLog(start=django.utils.timezone.now(),
                  file_path=os.path.abspath(self.chromosome_data), base_count=0, 
                  clip_count=0)
            else:
               self.import_log = ChromosomeBatchImportLog(start=django.utils.timezone.now(),
                  file_path=os.path.abspath(self.chromosome_data), base_count=0, 
                  clip_count=0)  
               self.import_log.batch = batch
               self.import_log.status = 'A'
               self.import_log.end = django.utils.timezone.now()
               self.import_log.calculate_run_time()
               if self.chromosome_data.split('.')[-1] == 'gz':
                   self.import_log.base_count = self.get_info(incl_rec_count=True)['bases_count']
               else:
                   self.import_log.base_count =  self.get_info(incl_rec_count=True)['rec_count']
               self.import_log.chromebase = None
               self.import_log.save()
    
    
            # Start transaction management.
            transaction.commit_unless_managed()
            transaction.enter_transaction_management()
            transaction.managed(True)
        
            # Make a new ChromosomeBase.
            self.cb = ChromosomeBase()
            self.cb.file_tag = ChromosomeBase.generate_file_tag()
            self.cb.start_position = self.cb.end_position = 0
            self.cb.release = self.flybase_release
        
            # Open our data files.
            self.data_file = open(self.cb.data_file_path, 'w')
            self.index_file = open(self.cb.index_file_path, 'wb')
            self.coverage_file = open(self.cb.coverage_file_path, 'w')  
            
            chromosome_reader = None

            print "Constructing ChromosomeBase object from file:\n%s" % \
                  self.chromosome_data
            print "  "

            try:

                if self.ref_chrom is not None:
                    self.cb.start_position = 1
                    try:
                        strains = Strain.objects.filter(is_reference=True,release__name=self.flybase_release)
                        self.cb.strain = strains[0]
                    except:
                        self.cb.strain = self._lookup_strain('Mesa Verde, CO 2-25 reference line')[0]

                    self.cb.chromosome = self._lookup_chromosome(self.ref_chrom)[0]

                elif self.chromosome_data.split('.')[-1] == 'gz':
                    vcf_reader = ChromosomeVCFImportFileReader(self.chromosome_data)
                    chrom,strain = vcf_reader.get_chrom_and_strain()
                    self.cb.start_position = 1
                    try:
                        self.cb.strain = StrainSymbol.objects.get(symbol=strain).strain
                    except:
                        print('Error - No strain: ' + str(strain))
                        raise Exception('Strain does not exist yet for : ' + strain)
                    self.cb.chromosome = self._lookup_chromosome(chrom)[0]
                else:
                    chromosome_reader = ChromosomeImportFileReader(self.chromosome_data)

                    if not chromosome_reader.format_parser:
                        # Unknown data format
                        # If the file isn't in the reference or standard data format,
                        # we can't do anything with it.
                        raise Exception('Unknown data format!')
                    else:
                       # Get the data we only want to think about once.
                        first_data = chromosome_reader.get_and_parse_next_line(reset=True)

                        if self.already_exists(first_data['strain_name'],first_data['chromosome_name']):
                           raise Exception('Chromosome Data for chromosome: %s and strain: %s exists already!' % (first_data['chromosome_name'],first_data['strain_name']))


                        self.cb.start_position = first_data['position']
                        self.cb.strain = self._lookup_strain(first_data['strain_name'])[0]
                        self.cb.chromosome = self._lookup_chromosome(
                          first_data['chromosome_name'])[0]

        
                # Save ChromosomeBase.
                self.cb.save()
                
                try:
                    if batch is None:
                        pass
                    else:
                        self.import_log.status = 'A'
                        self.import_log.end = django.utils.timezone.now()
                        self.import_log.calculate_run_time()
                        self.import_log.chromebase = self.cb
                        self.import_log.save()
                except:
                    raise

                vcf_meta_data = ''

                if self.ref_chrom is not None:
                    max_position = self.process_import_lines_ref()
                elif self.chromosome_data.split('.')[-1] == 'gz':
                    max_position, vcf_meta_data = self.process_import_lines_vcf(chrom,strain)
                else:
                    max_position = self.process_import_lines_psepileup(chromosome_reader)

                # Base and coverage sequences should now be fully constructed, so 
                # we can save the object.
                self.cb.end_position = max_position
                self.cb.save()
                  
                head, tail = os.path.split(self.chromosome_data)
                if chromosome_reader is None:
                    pass
                else:
                    chromosome_reader.finalise()
                destpath =  settings.PSEUDOBASE_CHROMOSOME_RAW_DATA_IMPORTED_PREFIX #'raw_data/chromosome/'
                
                print ('renaming: ',os.path.abspath(self.chromosome_data))
                print (' ..to: ',os.path.join(destpath,tail))
                os.rename(os.path.abspath(self.chromosome_data), os.path.join(destpath,tail)) 
                print ('Rename complete!')
                
                # Finish populating the import metadata.
                self.import_log.base_count = self.cb.total_bases
                self.import_log.vcf_meta_data = json.dumps(vcf_meta_data)
                self.import_log.end = django.utils.timezone.now()
                self.import_log.calculate_run_time()
                
                if (batch is None):
                    pass
                else:
                    self.import_log.chromebase = self.cb
                    self.import_log.status = 'C'
          
                # Only save the import metadata if we actually did anything.
                if self.import_log.base_count > 0:    
                    self.import_log.save()
            
            except:
                print ('in exception chromosome importer')
                self.data_file.close()
                self.index_file.close()
                self.coverage_file.close()
                os.remove(self.cb.data_file_path)
                os.remove(self.cb.index_file_path)
                os.remove(self.cb.coverage_file_path)
                
                if chromosome_reader:
                   chromosome_reader.finalise()
    
                transaction.rollback()
                transaction.leave_transaction_management()
                
                #rolled back everything else, but still put out import log entry showing fail
                self.import_log.status = 'F'
                self.import_log.end = django.utils.timezone.now()
                self.import_log.calculate_run_time()
                self.import_log.save()
    
                raise
    
            self.data_file.close()
            self.index_file.close()
            self.coverage_file.close()

            if chromosome_reader is None:
                pass
            else:
                chromosome_reader.finalise()
        
            # Finalize the transaction and close the db connection.
            transaction.commit()
            transaction.leave_transaction_management()
            connection.close()
        
#            # All lines of chromosome data have been processed, so we can print a 
#            # short summary of what we did.
#            td = self.import_log.end - self.import_log.start
#            print '\nProcessing complete in %s days, %s.%s seconds.' % \
#              (td.days, td.seconds, td.microseconds)
#            print '  ChromosomeBase objects constructed: 1'
#            print '  Total bases: %s' % self.import_log.base_count
#            print '  Total coverages clipped: %s' % self.import_log.clip_count            
            
    def print_summary(self):
#        # All lines of chromosome data have been processed, so we can print a 
#        # short summary of what we did.
         td = self.import_log.end - self.import_log.start
         print '\nProcessing complete in %s days, %s.%s seconds.' % \
           (td.days, td.seconds, td.microseconds)
         print '  ChromosomeBase objects constructed: 1'
         print '  Total bases: %s' % self.import_log.base_count
         print '  Total coverages clipped: %s' % self.import_log.clip_count
                    
