'''A custom Django administrative command for archiving off all project data (chromosomebase) for selected strain symbol

This command is intended to be used through Django's standard "management"
command interface, e.g.:

  # ./manage.py chromosome_move_project_dats_for_strain <strain_symbol dest_dir>


'''

from django.core.management.base import BaseCommand
from django.conf import settings
from optparse import make_option

from chromosome.models import ChromosomeBase
import shutil
import os

class Command(BaseCommand):
    '''A custom command to move project data files'''

    help = 'Move all project data for a strain to a specified archive directory'
    args = '<strain_symbol> <dest_dir>'


    def handle(self, strain_symbol,dest_dir, **options):
            '''The main entry point for the Django management command.

            '''
            print('symbol selected: ' + strain_symbol + ', dest dir selected: ' + dest_dir)

            cbs = ChromosomeBase.objects.get_all_chromosomebases_for_strain(strain_symbol)
            if len(cbs) == 0:
                print('No project data found for strain symbol: ' + strain_symbol)

            for cb in cbs:

                data_path = cb._get_data_file_path()
                if os.path.isfile(data_path):
                    dest_data_path = os.path.join(dest_dir, os.path.basename(data_path))
                    print('Moving: ' + str(cb.chromosome.name) + ' tag: ' + cb.file_tag + ' path: ',data_path, 'to: ',dest_data_path)
                    try:
                        shutil.move(data_path,dest_data_path)
                    except Exception as e:
                        print('Move failed from: ',data_path,' to: ',dest_data_path, ' error: ',e)
                else:
                    print('Does not exist: ' + str(cb.chromosome.name) + ' tag: ' + cb.file_tag + ' path: ',data_path)

                index_path = cb._get_index_file_path()
                if os.path.isfile(index_path):
                    dest_index_path = os.path.join(dest_dir, os.path.basename(index_path))
                    print('Moving: ' + str(cb.chromosome.name) + ' tag: ' + cb.file_tag + ' path: ',index_path, 'to: ',dest_index_path)
                    try:
                        shutil.move(index_path,dest_index_path)
                    except Exception as e:
                        print('Move failed from: ',index_path,' to: ',dest_index_path, ' error: ',e)
                else:
                    print('Does not exist: ' + str(cb.chromosome.name) + ' tag: ' + cb.file_tag + ' path: ',index_path)

                coverage_path = cb._get_coverage_file_path()
                if os.path.isfile(coverage_path):
                    dest_coverage_path = os.path.join(dest_dir, os.path.basename(coverage_path))
                    print('Moving: ' + str(cb.chromosome.name) + ' tag: ' + cb.file_tag + ' path: ',coverage_path, 'to: ',dest_coverage_path)
                    try:
                        shutil.move(coverage_path,dest_coverage_path)
                    except Exception as e:
                        print('Move failed from: ',coverage_path,' to: ',dest_coverage_path, ' error: ',e)
                else:
                    print('Does not exist: ' + str(cb.chromosome.name) + ' tag: ' + cb.file_tag + ' path: ',coverage_path)

