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

from django.conf import settings
from django.db import models
import django.utils.timezone
from django.db import connection, transaction
from django.db.models import Q


from common.models import Strain, StrainSymbol,Chromosome, ImportLog, ImportFileReader, BatchProcess


class ChromosomeBase(models.Model):
    '''Sequence Data and metadata about a particular chromosome.'''
    
    strain = models.ForeignKey(Strain)
    chromosome = models.ForeignKey(Chromosome)
    start_position = models.PositiveIntegerField()
    end_position = models.PositiveIntegerField()
    file_tag = models.CharField(max_length=32)

    pad_char = 'N' #For unknown bases outside bounds of self.start_position, self.end_position
    realign_char = '-'  # where insertions occur in a strain, re-align other strains padded with this char

  
    def __str__(self):
        '''Define the string representation of this class of object.'''
        return '%s %s' % (self.strain.name, self.chromosome)
  
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
        f = open(self.data_file_path)
    
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
            f.close()
    
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
        
        return r'>%s' % delimiter.join((self.strain.species.name,
          self.strain.name, self.chromosome.name,
          '%s..%s' % (start_position, end_position)))
        
  
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
        
        bases_str = ''
        for i,base in enumerate(bases):
            bases_str += bases[i]
            if (max_bases):
                if len(bases[i]) < max_bases[i]:
                   bases_str += ChromosomeBase.realign_char * (max_bases[i] - len(bases[i])) 
               
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
    def multi_strain_fasta(chromosome, species, start, end):
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
        for c in chromosomes:
            bases_per_position.append(c.get_bases_per_position(start,end))
        max_bases = ChromosomeBase.max_num_bases_per_position(bases_per_position)
 
    
    
        for c in chromosomes:
            if (len(chromosomes) < 2):
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
        ordering = ('strain__species__pk', 'chromosome__name', 'strain__name')


# Deprecated - now uses ChromosomeBatchImportLog
class ChromosomeImportLog(ImportLog):
    '''Metadata about the import of a particular ChromosomeBase object.'''
    
    base_count = models.PositiveIntegerField()
    clip_count = models.PositiveIntegerField()

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
    

class ChromosomeBatchImportProcess(BatchProcess):
    original_request = models.TextField()
    
    objects = ChromosomeBatchImportProcessManager()
    def num_files_in_batch(self):
        batchimports = self.chromosomebatchimportlog_set.all()  #ChromosomeBatchImportLog.objects.filter(batch=self.id)
        return len(batchimports)
    
    @staticmethod
    def create_batch_and_import_file(chromosome_data):
        #helper static method to create a batch and import single file within it
        transaction.commit_unless_managed()
        transaction.enter_transaction_management()
        transaction.managed(True)
        try:
               
            current_batches = ChromosomeBatchImportProcess.objects.current_batches() #ChromosomeBatchImportProcess.objects.filter(Q(batch_status='P') | Q(batch_status='I'))   
            if (len(current_batches) > 0):
               raise Exception('Batch import already in process. Please wait ')
            
            bp = ChromosomeBatchImportProcess(submitted_at = django.utils.timezone.now(),batch_status = 'P')
            
            orig_req = ''
            abs_path = os.path.abspath(chromosome_data)
            orig_req += abs_path

            bp.original_request = orig_req  
            bp.save()
           
            
            bp.start()
            bp.save()
            chr_importer = ChromosomeImporter(chromosome_data)
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
    chromebase = models.ForeignKey(ChromosomeBase,null=True,blank=True)


    
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
        
        return [line[0], line[1], int(line[2]), 1, line[3].upper()]

    def _standard_format(self, line):
        '''Parse a line in "standard" format and return a list of the data.
      
        The "standard" format is 4 tab-delimited fields.  The third field
        contains three space-delimited values.  The first column is empty.
      
        '''
        #pdb.set_trace()
        replace_whitespace = re.compile(r'\s').sub
        base_info = line[3].split(' ', 2)
        return [str(line[1]), str(line[2]), int(base_info[0]), 
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
        
class ChromosomeImporter():
#Not a database table

    def __init__(self,chromosome_data):
            self.chromosome_data = chromosome_data
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
        return (Chromosome.objects.get(name=chromosome), False)
  
    def _coverage_index(self, n):
        '''Pack n into a byte for use in the coverage index.'''
        return struct.pack('B', n)
  
    def _index(self, n):
        '''Pack n into an integer for use in the base index.'''
        return struct.pack('I', n)


    def get_info(self,incl_rec_count = False):

            chromosome_reader = None
            
            try:
                chromosome_reader = ChromosomeImportFileReader(self.chromosome_data)
     
                if not chromosome_reader.format_parser:
                   return {'file_name':self.chromosome_data_fname,'format':'unknown'} 
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
             
            except:
                print ('whoops exc')
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
        
            # Open our data files.
            self.data_file = open(self.cb.data_file_path, 'w')
            self.index_file = open(self.cb.index_file_path, 'wb')
            self.coverage_file = open(self.cb.coverage_file_path, 'w')  
            
            chromosome_reader = None
        
            try:
                print "Constructing ChromosomeBase object from file:\n%s" % \
                  self.chromosome_data
                print "  "
    
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
                    
            
                # Base and coverage sequences should now be fully constructed, so 
                # we can save the object.
                self.cb.end_position = max_position
                self.cb.save()
                  
                # Finish populating the import metadata.
                self.import_log.base_count = self.cb.total_bases
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
                    
                head, tail = os.path.split(self.chromosome_data) 
                chromosome_reader.finalise()
                destpath = './raw_data/chromosome'
                print ('renaming: ',os.path.abspath(self.chromosome_data))
                print (' ..to: ',os.path.join(destpath,tail))
                os.rename(os.path.abspath(self.chromosome_data), os.path.join(destpath,tail)) 
                print ('Rename complete!')
            
            except:
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
    
                raise
    
            self.data_file.close()
            self.index_file.close()
            self.coverage_file.close()
            
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
                    
