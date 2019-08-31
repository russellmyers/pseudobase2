'''Models for the common application.'''

import os
import shutil
import csv

import django.utils.timezone
from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
import datetime


class Species(models.Model):
    '''Data about a particular species.'''

    name = models.CharField(max_length=255)
    symbol = models.CharField(max_length=16)
  
    def __str__(self):
        '''Define the string representation of this class of object.'''
        return '%s (%s)' % (self.name, self.symbol)
  
    class Meta:
        '''Define Django-specific metadata.'''
        verbose_name_plural = 'species'


class Release(models.Model):
    '''Flybase releases which strains are aligned against.'''

    name = models.CharField(max_length=20)
    description = models.CharField(max_length=255)

    def __str__(self):
        '''Define the string representation of this class of object.'''
        return '%s, %s' % (self.name, self.description)


class Strain(models.Model):
    '''Data about a particular strain.'''

    name = models.CharField(max_length=255)
    species = models.ForeignKey(Species)
    release = models.ForeignKey(Release,null=True)
    is_reference = models.BooleanField()

    def __str__(self):
        '''Define the string representation of this class of object.'''
        rel = 'Norel' if self.release is None else self.release.name
        return '%s, %s, %s' % (self.name, rel, self.species.name)
    
    @property
    def formatted_info(self):
        strain_info = self.name
        try:
            if self.straincollectioninfo:
                strain_info += ', '
                strain_info += self.straincollectioninfo.formatted_info
        except:
            pass 
        return strain_info
    
    def num_chromosomes(self):
        from chromosome.models import ChromosomeBase
        chrom_bases = ChromosomeBase.objects.filter(strain = self)
        return len(chrom_bases)
    
    @property
    def formatted_chromosomes_info(self):
        chrom_info = ''
        num = self.num_chromosomes()
        chrom_info += ' (' + str(num) + ' chromosome'
        if (num != 1):
            chrom_info += 's'
        chrom_info += ')'  
        return chrom_info    
  
        

class StrainCollectionInfo(models.Model):
    strain = models.OneToOneField(
        Strain,
        on_delete=models.PROTECT
    )
    year = models.PositiveIntegerField(
            blank=True,
            null=True,
            validators=[
                MinValueValidator(1900), 
                MaxValueValidator(datetime.datetime.now().year)],
            help_text="Use the following format: <YYYY>")
    info = models.TextField(blank=True)
    
    class Meta:
        verbose_name_plural = 'Strain collection info'
    
    def __str__(self):
        return '%s' % (self.strain.name)
    
    @property    
    def formatted_info(self):
        strain_info = ''

        if (self.year is not None):
           strain_info += 'collected: ' + str(self.year)
        if (len(self.info) > 0):
           if (len(strain_info) > 0):
               strain_info += ', '
           strain_info += self.info
           
        return strain_info    

class StrainSymbol(models.Model):
    '''Short symbols identifying a strain, used for importing mainly. Can be many symbols mapping to one strain.'''
    symbol = models.CharField(max_length=255,unique=True)
    strain = models.ForeignKey(Strain)

    def __str__(self):
        '''Define the string representation of this class of object.'''
        rel = 'Norel' if self.strain.release is None else self.strain.release.name
        return '%s [%s, %s, %s]' % (self.symbol, self.strain.name, rel, self.strain.species.symbol)



class Chromosome(models.Model):
    '''Data about a particular chromosome.'''

    name = models.CharField(max_length=255)

    def __str__(self):
        '''Define the string representation of this class of object.'''
        return self.name


class ImportLog(models.Model):
    '''Metadata about import processes.
    
    NOTE: This class is abstract and should only be used as a basis for more
    specific models.
    
    '''
    
    start = models.DateTimeField()
    end = models.DateTimeField()
    run_microseconds = models.PositiveIntegerField()
    file_path = models.CharField(max_length=1024)
  
    def calculate_run_time(self):
        '''Calculate how many microseconds have elapsed during the import.'''
        
        td = self.end - self.start
        self.run_microseconds = (86400 * td.days + td.seconds) * \
          1000000 + td.microseconds
        return self.run_microseconds
  
    class Meta:
        '''Define Django-specific metadata.'''
        abstract = True


class BatchProcess(models.Model):
    '''Metadata about batch processes and their handling.
    
    NOTE: This class is abstract and should only be used as a basis for more
    specific models.
    
    '''

    submitter_email = models.EmailField(null = True)
    submitted_at = models.DateTimeField()
    # Available status codes for batch_status:
    # P = Pending (has yet to be processed)
    # A = Active (processing)
    # F = Failed (processing was attempted, but an unknown failure occurred)
    # C = Completed (has been processed, but not yet included in a report)
    # R = Reported (has been processed and included in a report)
    # E = Expired (associated delivery files have been removed)
    batch_status = models.CharField(max_length=1, db_index=True, default='P')
    batch_start = models.DateTimeField(null=True)
    batch_end = models.DateTimeField(null=True)
    final_report = models.TextField()
    delivery_tag = models.CharField(max_length=32, null=True)
    expiration = models.DateTimeField(null=True)

    def start(self, batch_status='A'):
        '''Start the proccessing of this job.'''
        
        self.batch_start = django.utils.timezone.now()
        self.batch_status = batch_status

    def stop(self, batch_status='C'):
        '''Stop the processing of this job.'''
        
        self.batch_end = django.utils.timezone.now()
        self.batch_status = batch_status
  
    def full_delivery_url(self, site='pseudobase.biology.duke.edu', 
      protocol='http'):
        '''Return a the full URL of the results created by this process.'''
    
        if protocol and not protocol.endswith('://'):
            protocol = '%s://' % protocol
      
        return '%s%s%s%s/%s' % (
          protocol,
          site,
          settings.PSEUDOBASE_RESULTS_PREFIX,
          self.delivery_tag,
          settings.PSEUDOBASE_RESULTS_FILENAME
        )
  
    def expire_delivery(self):
        '''Remove the results created by this process from the filesystem.
        
        Returns whether any results were removed.
        
        '''

        removed = False
        delivery_path = os.path.join(settings.PSEUDOBASE_DELIVERY_ROOT,
          self.delivery_tag)
        if os.path.exists(delivery_path):
            shutil.rmtree(delivery_path)
            removed = True
        return removed
  
    class Meta:
        '''Define Django-specific metadata.'''
        abstract = True

__metaclass__ = type
class ImportFileReader():
# Not a database table
      
      def __init__(self,fPath,target_field_names=None):
          self.fPath = fPath

          self.field_names = target_field_names 
           
          self.inFile = open(self.fPath)
          self.format_parser = self._determine_format_parser()
          
          #Ensure file is at beginning
          self.inFile.seek(0) 
          self.reader = csv.reader(self.inFile, delimiter='\t')

      def get_num_records(self):
 
          #Ensure file is at beginning
          self.inFile.seek(0)     
          count_reader = csv.reader(self.inFile, delimiter='\t')
          row_count = sum(1 for row in count_reader)
          
          self.inFile.seek(0)   
          
          return row_count
     
      def parse_line(self,line):
          
          if line is None:
             return None 
          
          data = dict(zip(self.field_names, self.format_parser(line)))
          
          return data
      
      def get_next_line(self,reset=False):
         
          if (reset):
              self.inFile.seek(0) 
              self.reader = csv.reader(self.inFile, delimiter='\t')
         
          try:  
              line = self.reader.next()
              return line
              
          except:
              return None 
        
      def get_and_parse_next_line(self,reset=False):
          
          line = self.get_next_line(reset)
          
          return self.parse_line(line)

          
      def _get_first_line(self):
          self.inFile.seek(0) 
          reader = csv.reader(self.inFile, delimiter='\t')
         
          try:  
              line = reader.next()
              return line
          except:
              return None
          
    
      def  dummy_format_parser(self,line):
         return line                            
        
     
          
      def _determine_format_parser_from_example_line(self,example_line):
          if example_line is None:
              return None
          
          if (self.field_names is None):
              self.field_names = []
              for i in range (len(example_line)):
                  self.field_names.append('f' + str(i))
                  
        
          return self.dummy_format_parser
          
         
          
      def _determine_format_parser(self):
#          pdb.set_trace()
          example_line = self._get_first_line()
          
          format_parser = self._determine_format_parser_from_example_line(example_line)
 
          return format_parser
              
          
      def is_valid(self):
          return self.format_parser is not None
      
      def finalise(self):
          self.inFile.close()