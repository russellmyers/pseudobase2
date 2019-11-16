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
    #args = '<path to VCF file>'

    option_list = BaseCommand.option_list + (
        make_option('-f', '--filter',
                    dest='filter',
                    action="store_true",
                    default=False,
                    help='Also create file filtered to only called variants for strain (SNPS and INDELS'),
        make_option('-i', '--indels',
                    dest='indels',
                    action="store_true",
                    default=False,
                    help='Also create file filtered to only called  INDEL variants for strain'),
        make_option('-l', '--filelist',
                    dest='file_list',
                    action="append",
                    default=[],
                    help='List of files to split'),

    )

    def assemble_input_file_name_components(self, file_name):
        path,name = os.path.split(file_name)
        chrom_part = name.split('_forPseudobase')[0]
        ext_part = '_forPseudobase' + name.split('_forPseudobase')[1]
        species_strain_part = ext_part.split('SNPS-INDELS_')[1]
        species_strain = species_strain_part.split('.')[0]
        chrom = chrom_part.split('chr')[1]
        return path,ext_part,chrom, species_strain

    def assemble_output_file(self, chrom, output_folder, ext_part, species_strain,filtered=False,indels=False):

        # file_name = 'genotyped_filtered'
        # file_name += 'ALL'
        # file_name += '_' + strain + '_chr' + chrom + '.vcf.gz'
        file_path = os.path.join(output_folder,species_strain)
        if filtered:
            file_path = os.path.join(file_path,'filtered')
        elif indels:
            file_path = os.path.join(file_path, 'indels')
        else:
            file_path = os.path.join(file_path, 'split')

        if not os.path.exists(file_path):
            os.makedirs(file_path)

        if filtered:
            first_part = ext_part.split('.vcf.gz')[0]
            file_path_and_name = os.path.join(file_path, 'chr' + chrom + first_part + '_filtered' + '.vcf.gz')
        elif indels:
            first_part = ext_part.split('.vcf.gz')[0]
            file_path_and_name = os.path.join(file_path, 'chr' + chrom + first_part + '_indels_only' + '.vcf.gz')
        else:
            file_path_and_name = os.path.join(file_path, 'chr' + chrom + ext_part)
        return file_path_and_name


    def split(self,file_name,ext_part,path,species_strain,reduce=False,indels=False):
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
                #sys.stdout.write('.')
                #sys.stdout.flush()
                self.stdout.write(' Processing: ' + str(i))


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

                if skip_this_record or v.is_het():
                    line_simplified = line
                else:
                    line_simplified = v.simplify_alts()

                if v.CHROM in chroms:
                       #chroms[v.CHROM].append(line)
                       f = chroms[v.CHROM]['file']
                       f.write('\n')
                       f.write(line.encode())
                       chroms[v.CHROM]['records'] +=1
                       if reduce and not skip_this_record:
                           f_filtered = chroms[v.CHROM]['filtered_file']
                           f_filtered.write('\n')
                           f_filtered.write(line_simplified.encode())
                           chroms[v.CHROM]['filtered_records'] += 1
                       if indels and not skip_this_record and (var_type ==  'I' or var_type == 'D'):
                           f_indels = chroms[v.CHROM]['indel_file']
                           f_indels.write('\n')
                           f_indels.write(line_simplified.encode())
                           chroms[v.CHROM]['indel_records'] += 1


                else:
                       #chroms[v.CHROM] = [line]
                       file_name = self.assemble_output_file(v.CHROM,path,ext_part,species_strain)
                       print('Creating out file name: ' + file_name)
                       f = gzip.open(file_name, 'wb')
                       chroms[v.CHROM] = {'file': f, 'records': 1}
                       out_comments_str = '\n'.join(comments)
                       f.write(out_comments_str)
                       f.write('\n')
                       f.write(line.encode())
                       if reduce:
                           file_name_filtered = self.assemble_output_file(v.CHROM, path, ext_part, species_strain,filtered=True)
                           print('Creating filtered out file name: ' + file_name_filtered)
                           f_filtered = gzip.open(file_name_filtered, 'wb')
                           chroms[v.CHROM]['filtered_file'] =  f_filtered
                           f_filtered.write(out_comments_str)
                           if skip_this_record:
                               chroms[v.CHROM]['filtered_records'] = 0
                           else:
                               chroms[v.CHROM]['filtered_records'] = 1
                               f_filtered.write('\n')
                               f_filtered.write(line_simplified.encode())
                       if indels:
                           file_name_indels = self.assemble_output_file(v.CHROM, path, ext_part, species_strain, indels=True)
                           print('Creating indels out file name: ' + file_name_indels)
                           f_indels = gzip.open(file_name_indels, 'wb')
                           chroms[v.CHROM]['indel_file'] = f_indels
                           f_indels.write(out_comments_str)
                           if skip_this_record or not (var_type == 'I' or var_type == 'D') :
                               chroms[v.CHROM]['indel_records'] = 0
                           else:
                               chroms[v.CHROM]['indel_records'] = 1
                               f_indels.write('\n')
                               f_indels.write(line_simplified.encode())






        print(' ')
        print(' Num comment lines: ' + str(len(comments)))
        if reduce:
            print(' Ignoring for filtered file:')
            print('   Not passed: ' + str(not_passed))
            print('   Hom Ref: ' + str(hom_ref))
            print('   Uncalled: ' + str(not_called))
            print('   *: ' + str(stars))
        for chrom in chroms:
            print(' chrom: ' + chrom + ' records: ' + str(chroms[chrom]['records'])  +  ' - closing ')
            f = chroms[v.CHROM]['file']
            f.close()
            if reduce:
                print(' chrom: ' + chrom + ' filtered records: ' + str(chroms[chrom]['filtered_records']) + ' - closing ')
                f = chroms[v.CHROM]['filtered_file']
                f.close()
            if indels:
                print(' chrom: ' + chrom + ' indel records: ' + str(chroms[chrom]['indel_records']) + ' - closing ')
                f = chroms[v.CHROM]['indel_file']
                f.close()


        print(' Finished reading vcf. Num records: ' + str(i))


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

    def handle(self,  **options):
            '''The main entry point for the Django management command.

            '''

            self.stdout.write('Number of files to process: ' + str(len(options['file_list'])))
            self.stdout.write('Also create reduced VCF with called variants only (SNPS and INDELS) for strain: ' + str(options['filter']))
            self.stdout.write('Also create reduced VCF with called INDEL variants only for strain: ' + str(options['indels']))

            for file_name in options['file_list']:
                path,ext_part,in_chrom,species_strain = self.assemble_input_file_name_components(file_name)
                self.stdout.write('*******************')
                self.stdout.write(' Input file: ' + file_name)
                self.stdout.write(' Chrom group: ' + in_chrom)
                self.stdout.write(' Species/Strain: ' + species_strain)


                chroms,comments = self.split(file_name,ext_part,path,species_strain,reduce=options['filter'],indels=options['indels'])

            # for chrom in chroms:
            #       out_name = self.assemble_output_file(chrom,path,ext_part,species_strain)
            #       self.output_file(out_name,comments,chroms[chrom])






