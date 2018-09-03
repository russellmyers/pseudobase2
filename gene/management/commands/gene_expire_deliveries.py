'''A custom Django administrative command for expiring delivery files.

This command removes all files associated with a delivery if it is past its
expiration date.  This should be run from cron at least once a week, but once
a day would be appropriate.

'''

import django.utils.timezone
from django.core.management.base import BaseCommand
from django.db import connection, transaction

from gene.models import GeneBatchProcess


class Command(BaseCommand):
    '''A custom command to remove expired delivery files.'''
    
    def _expire_deliveries(self):
        '''Find and expire eligible delivery files.'''
    
        for gbp in GeneBatchProcess.objects.filter(batch_status='R').filter(
          expiration__lt=django.utils.timezone.now()):
            gbp.expire_delivery()

            # The "E" status code means the process has been expired.
            gbp.batch_status = 'E'
            gbp.save()
    
    def handle(self, **options):
        '''The main entry point for the Django management command.
      
        Finds all GeneBatchProcess objects that haven't yet been expired and
        expires them.  All GeneBatchProcess objects that have been reported on 
        and are beyond their expiration date are eligible.
        
        '''

        # Start transaction management.
        transaction.commit_unless_managed()
        transaction.enter_transaction_management()
        transaction.managed(True)

        try:
            self._expire_deliveries()
        except:
            transaction.rollback()
            transaction.leave_transaction_management()
            raise

        # Finalize the transaction and close the db connection.
        transaction.commit()
        transaction.leave_transaction_management()
        connection.close()
