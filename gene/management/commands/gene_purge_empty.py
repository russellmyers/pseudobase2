'''A custom Django administrative command for purging "empty" genes.

This command is used to prune gene entries in the database which do not 
contain useful information.  At present, this means any gene which contains 
exclusively "N" or "-".  These genes are removed because including them in the
FASTA output generally breaks downstream processing programs.

The command outputs a line for each gene it removes, so that the data for the 
appropriate gene can be located by the researchers and re-entered if 
available.

NOTE: The algorithm for determining the empty state is currently very naive.
It gets the length of the sequence of bases for the gene, and tests to see if 
the sequence either matches (len * "N") or (len * "-").  This is because doing
a per-character test for each gene (of which there are over 300k at present) 
would be prohibitively expensive.  This means we'll miss any genes that are a 
combination of "N" and "-".

NOTE: This can take a while to run, since it still has to iterate over every 
gene in the system.  However, since the script doesn't need to be run very 
often (really, only after any imports) we don't particularly care.

'''

import sys

from django.core.management.base import BaseCommand
from django.db import connection, transaction

from gene.models import Gene

class Command(BaseCommand):
    '''A custom command to purge genes with "empty" base sequences.'''

    def handle(self, **options):
        '''The main entry point for the Django management command.
        
        Finds all Gene objects with base sequences that are "empty" as defined
        by the Noor lab and removes them from the database.
    
        '''

        # Start transaction management.
        transaction.commit_unless_managed()
        transaction.enter_transaction_management()
        transaction.managed(True)

        for g in Gene.objects.all():
            l = len(g.bases)
            d_str = l * '-'
            n_str = l * 'N'
            if g.bases == d_str or g.bases == n_str:
                sys.stdout.write(
                  'Gene: %s, Chromosome: %s, Strain: %s, Start: %s\n' % (
                    g.import_code, g.chromosome.name, g.strain.name, 
                    g.start_position))
                sys.stdout.flush()
                g.delete()
        
        # Finalize the transaction and close the db connection.
        transaction.commit()
        transaction.leave_transaction_management()
        connection.close()
