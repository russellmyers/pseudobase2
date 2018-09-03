'''Models for the common application.'''

import os
import shutil

import django.utils.timezone
from django.conf import settings
from django.db import models


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


class Strain(models.Model):
    '''Data about a particular strain.'''

    name = models.CharField(max_length=255)
    species = models.ForeignKey(Species)
    is_reference = models.BooleanField()

    def __str__(self):
        '''Define the string representation of this class of object.'''
        return '%s, %s' % (self.name, self.species.name)


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
