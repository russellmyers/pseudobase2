'''A custom Django administrative command for splitting a VCF file into a separate file for each chromosome contained within it

This command is intended to be used through Django's standard "management"
command interface, e.g.:

  # ./manage.py vcf_split <chrom strain>


'''

from django.core.management.base import BaseCommand
from django.conf import settings
from optparse import make_option
import os
from chromosome.models import ChromosomeVCFImportFileReader
from chromosome.utils import VCFRecord
import gzip
import sys

from chromosome import utils


class Command(BaseCommand):
    '''A custom command to convert VCF to psepileup format'''

    help = 'Split a vcf file into separate files per chromosome'
    args = '<path to VCF file>'

    option_list = BaseCommand.option_list + (
        make_option('-f', '--filter',
                    dest='filter',
                    action="store_true",
                    default=False,
                    help='reduce to called variants for strain only'),
    )

    def assemble_input_file_name_components(self, file_name):
        path,name = os.path.split(file_name)
        chrom_part = name.split('_forPseudobase')[0]
        ext_part = '_forPseudobase' + name.split('_forPseudobase')[1]
        species_strain_part = ext_part.split('SNPS-INDELS_')[1]
        species_strain = species_strain_part.split('.')[0]
        chrom = chrom_part.split('chr')[1]
        return path,ext_part,chrom, species_strain

    def assemble_output_file(self, chrom, output_folder, ext_part, species_strain):

        # file_name = 'genotyped_filtered'
        # file_name += 'ALL'
        # file_name += '_' + strain + '_chr' + chrom + '.vcf.gz'
        file_path = os.path.join(output_folder,species_strain)

        if not os.path.exists(file_path):
            os.makedirs(file_path)

        file_path_and_name = os.path.join(file_path, 'chr' + chrom + ext_part)
        return file_path_and_name


    def split(self,file_name,reduce=False):
        vcf_reader = ChromosomeVCFImportFileReader(file_name)
        vcf_reader.open()
        comments = []
        lines = []
        chroms = {}

        not_passed = 0
        not_called = 0
        hom_ref = 0
        stars = 0

        for i, line in enumerate(vcf_reader.vcf_file):
            if i % 250000 == 0:
                sys.stdout.write('.')
                sys.stdout.flush()



            line = line.decode('utf-8').rstrip()
            if line[:1] == '#':
                comments.append(line)
            else:

                v = VCFRecord(line)
                #
                # summary_flags = v.summary_flags()
                var_type, called_bases, read_depth = v.var_type()

                skip_this_record = False

                if not (v.passed_filter()):
                    not_passed +=1
                    skip_this_record = True
                elif var_type == 'R':
                    hom_ref +=1
                    skip_this_record = True
                elif var_type == 'U':
                    not_called +=1
                    skip_this_record = True
                elif var_type == '*':
                    stars +=1
                    skip_this_record = True

                if reduce and skip_this_record:
                    pass
                else:
                   if v.CHROM in chroms:
                       chroms[v.CHROM].append(line)
                   else:
                       chroms[v.CHROM] = [line]
                   lines.append(line)

        print(' ')
        print('Num comment lines: ' + str(len(comments)))
        if reduce:
            print('Ignoring:')
            print('  Not passed: ' + str(not_passed))
            print('  Hom Ref: ' + str(hom_ref))
            print('  Uncalled: ' + str(not_called))
            print('  *: ' + str(stars))
        for chrom in chroms:
            print('chrom: ' + chrom + ' ' +  str(len(chroms[chrom])) + ' called variants')



        print('Finished reading vcf. Num records: ' + str(i))


        vcf_reader.close()

        return chroms,comments

    def output_file(self,file_name,comments,contents):

        out_comments_str = '\n'.join(comments)

        out_vcf_str = '\n'.join(contents)

        out_str = '\n'.join([out_comments_str, out_vcf_str])

        print('Writing: ' + file_name)


        f = gzip.open(file_name, 'wb')
        f.write(out_str.encode())
        f.close()

    def handle(self, file_name, **options):
            '''The main entry point for the Django management command.

            '''

            path,ext_part,in_chrom,species_strain = self.assemble_input_file_name_components(file_name)
            self.stdout.write('Input file: ' + file_name)
            self.stdout.write('Chrom group: ' + in_chrom)
            self.stdout.write('Species/Strain: ' + species_strain)
            self.stdout.write('Reduce to called variants only for strain: ' + str(options['filter']))

            chroms,comments = self.split(file_name,reduce=options['filter'])

            for chrom in chroms:
                  out_name = self.assemble_output_file(chrom,path,ext_part,species_strain)
                  self.output_file(out_name,comments,chroms[chrom])






