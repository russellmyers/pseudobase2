'''Models for the chromosome application.'''

import array
import base64
import os
import random
import re
import string
import struct
import textwrap

from django.conf import settings
from django.db import models

from common.models import Strain, Chromosome, ImportLog


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


class ChromosomeImportLog(ImportLog):
    '''Metadata about the import of a particular ChromosomeBase object.'''
    
    base_count = models.PositiveIntegerField()
    clip_count = models.PositiveIntegerField()
