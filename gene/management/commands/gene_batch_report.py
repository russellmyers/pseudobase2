'''A custom Django administrative command for reporting "gene batch" requests.

This command causes Django to send an e-mail report giving brief information
about any "batch gene" requests that were submitted since the last time the
report was run.  This should ideally be run from cron.

'''

import textwrap

import django.utils.timezone
from django.core.mail import mail_managers,  EmailMessage
from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.conf import settings

from gene.models import GeneBatchProcess

class Command(BaseCommand):
    '''A custom command to send an e-mail report about batch gene requests.'''

    def _generate_report(self):
        '''Generate the text of the report.'''
        report_lines = []
        report_count = 1
        for gbp in GeneBatchProcess.objects.filter(batch_status='C'):
            report_lines.append('%d) Request by %s: %d total, %d failures' % (
              report_count, gbp.submitter_email, gbp.total_symbols, 
              gbp.failed_symbols))
            report_lines.append('\nExample genes:\n%s' % '\n'.join(
              textwrap.TextWrapper(width=75).wrap(', '.join(
                gbp.original_request.split('\n')[0:5]))))
            report_lines.append('')
      
            # The "R" status code means the process has been reported on.
            gbp.batch_status = 'R'
            gbp.save()
            report_count += 1
        return report_lines

    def handle(self, **options):
        '''The main entry point for the Django management command.
      
        Finds all GeneBatchProcess objects that haven't yet been reported on 
        andcontructs a report from them.  The report is e-mailed to all the 
        people defined as "managers" for the project.
      
        '''

        # Start transaction management.
        transaction.commit_unless_managed()
        transaction.enter_transaction_management()
        transaction.managed(True)

        try:
            report_lines = self._generate_report()
            if report_lines:
                date_report = django.utils.timezone.now()
                # mail_managers(
                #   'Pseudobase report: Batch gene requests - %s' % (
                #     date_report.date()),
                #   'The following batch gene requests were submitted since '
                #   'the last report:\n\n%s\n' % '\n'.join(report_lines))
                email = EmailMessage(
                    'Pseudobase report: Batch gene requests - %s' % (
                        date_report.date()),
                    'The following batch gene requests were submitted since '
                    'the last report:\n\n%s\n' % '\n'.join(report_lines),
                    'django @ biology.duke.edu',
                    [address for name, address in settings.MANAGERS],
                    []
                )
                email.send(fail_silently=False)

        except:
            transaction.rollback()
            transaction.leave_transaction_management()
            raise

        # Finalize the transaction and close the db connection.
        transaction.commit()
        transaction.leave_transaction_management()
        connection.close()
