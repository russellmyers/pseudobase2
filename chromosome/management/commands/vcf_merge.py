'''A custom Django administrative command for merging two VCF files (typically SNP and INDEL).

This command is intended to be used through Django's standard "management"
command interface, e.g.:

  # ./manage.py vcf_merge <chrom strain>


'''

from django.core.management.base import BaseCommand
from django.conf import settings
from optparse import make_option
import os

from chromosome import utils


class Command(BaseCommand):
    '''A custom command to convert VCF to psepileup format'''

    help = 'Merges two vcf files, typically SNP and INDEL file.'
    args = '<chrom strain>'

    option_list = BaseCommand.option_list + (
        make_option('-f','--output_folder',
                    dest='output_folder',
                    default=settings.PSEUDOBASE_CHROMOSOME_RAW_DATA_VCF_PREFIX,
                    help='output file folder'),
    )  + (
        make_option('-1', '--inputfile1',
                    dest='input_file_1',
                    help='Optional - input file name 1. Derived if not input'),

    )  + (
        make_option('-2', '--inputfile2',
                    dest='input_file_2',
                    help='Optional - input file name 2. Derived if not input'),

    )


    def assemble_default_input_file(self,chrom,strain,type):
        file_name =  'genotyped_filtered'
        file_name  +=  type
        file_name += '_' + strain + '_chr' +   chrom + '.vcf.gz'
        file_path_and_name = os.path.join(settings.PSEUDOBASE_CHROMOSOME_RAW_DATA_VCF_PREFIX,file_name)
        return file_path_and_name

    def assemble_default_output_file(self, chrom, strain,output_folder):
        file_name = 'genotyped_filtered'
        file_name += 'ALL'
        file_name += '_' + strain + '_chr' + chrom + '.vcf.gz'
        file_path_and_name = os.path.join(output_folder, file_name)
        return file_path_and_name


    def handle(self, chrom, strain, **options):
        '''The main entry point for the Django management command.

        '''

        if options['input_file_1'] is None:
            input_file_1 = self.assemble_default_input_file(chrom,strain,'SNPS')
            self.stdout.write('No input file 1. Using default: ' + input_file_1)
        else:
            input_file_1 = options['input_file_1']

        if options['input_file_2'] is None:
            input_file_2 = self.assemble_default_input_file(chrom, strain,'INDELS')
            self.stdout.write('No input file 2. Using default: ' + input_file_2)
        else:
            input_file_2 = options['input_file_2']

        output_file = self.assemble_default_output_file(chrom,strain,options['output_folder'] )

        self.stdout.write(self.style.SUCCESS('Input file 1: ' + input_file_1))
        self.stdout.write(self.style.SUCCESS('Input file 2: ' + input_file_2))
        self.stdout.write(self.style.SUCCESS('Output file ' + output_file))

        utils.merge_vcfs(input_file_1,input_file_2,output_file)

        self.stdout.write(self.style.SUCCESS('VCF merge complete. Chrom: ' +  chrom + ' Strain: ' + strain))

