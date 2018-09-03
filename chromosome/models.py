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
  
    def __str__(self):
        '''Define the string representation of this class of object.'''
        return '%s %s' % (self.strain.name, self.chromosome)
  
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
  
    def _get_byte_offset_from_index(self, n):
        '''Look up the byte offset of the data in position n from the index.
        
        The index file keeps track of the number of bytes from the start of
        the data file where any particular position begins.
        
        '''
    
        format = 'I'
        format_size = struct.calcsize(format)

        f = open(self.index_file_path)

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

        error_data = []
        if not self.valid_position(start_position):
            error_data.append(
              'Invalid start position (%s); must be at least %s.' % \
                (start_position, self.start_position))
        if not self.valid_position(end_position):
            error_data.append(
              'Invalid end position (%s); must be no more than %s.' % \
                (end_position, self.end_position))

        if error_data:
            return error_data
        else:
            start = self._position_offset(start_position)
            end = self._position_offset(end_position)
            bases = self._base_data(self._position_offset(start_position),
              self._position_offset(end_position))
      
            if wrapped:
                # We have to go through this little eval dance because the
                # "break_on_hyphens" keyword arg only exists in python 2.6+.
                try:
                    eval('textwrap.TextWrapper(break_on_hyphens=False)')
                    tw = textwrap.TextWrapper(width=75, 
                      break_on_hyphens=False)
                except TypeError:
                    tw = textwrap.TextWrapper(width=75)
                return tw.wrap(bases)
            else:
                return bases
 
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
    
        for c in chromosomes:
            yield (c.fasta_header(start, end), c.fasta_bases(start, end))
  
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
