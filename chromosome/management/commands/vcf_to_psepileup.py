'''A custom Django administrative command for analysing a VCF (and relevant reference sequence)
 and converting to psepileup format

This command is intended to be used through Django's standard "management"
command interface, e.g.:

  # ./manage.py vcf_to_psepileup <chrom strain>


'''

from django.core.management.base import BaseCommand
from django.conf import settings
from optparse import make_option
import os

from chromosome import utils


class Command(BaseCommand):
    '''A custom command to convert VCF to psepileup format'''

    help = 'Converts vcf file to custom Noor lab psepileup format ready for import into Pseudobase.'
    args = '<chrom strain>'

    option_list = BaseCommand.option_list + (
        make_option('-f','--output_folder',
                    dest='output_folder',
                    default=settings.PSEUDOBASE_CHROMOSOME_RAW_DATA_PENDING_PREFIX,
                    help='output file folder for psepileup'),
    )  + (
        make_option('-i', '--input_file',
                    dest='input_file',
                    help='Optional - input VCF file name. Derived if not input'),

    )  + (
        make_option('-n', '--num_recs',
                    dest='num_recs',
                    help='Optional - restricts to this number of records for testing'),

    )


    def assemble_default_input_file(self,chrom,strain,type):
        file_name =  'genotyped_filtered'
        file_name  +=  type
        file_name += '_' + strain + '_chr' +   chrom + '.vcf.gz'
        file_path_and_name = os.path.join(settings.PSEUDOBASE_CHROMOSOME_RAW_DATA_VCF_PREFIX,file_name)
        return file_path_and_name

    def assemble_default_output_pse_file(self, chrom, strain,output_folder):
        file_name = chrom + '_' + strain + '.psepileup'
        file_path_and_name = os.path.join(output_folder, file_name)
        return file_path_and_name

    def assemble_default_output_vcf_file(self, chrom, strain,type, output_folder):
        file_name = 'genotyped_filtered'
        file_name += type
        file_name += '_' + strain + '_chr' + chrom + '.vcf.gz'
        file_path_and_name = os.path.join(output_folder, file_name)
        return file_path_and_name

    def process_vcf_all_steps(self,file_type_1, file_name_1, release, org, chrom, out_pse_full_name,
                                  out_vcf_full_name, file_type_2=None, file_name_2=None, num_recs=None,
                                  base_density=100000,
                                  show_plots=False):
            df, comments_1, comments_2 = utils.read_vcfs(file_type_1, file_name_1, release, file_type_2=file_type_2,
                                                   file_name_2=file_name_2, num_recs=num_recs)

            dup = utils.vcf_duplicate_positions(df)

            df = utils.analyse_vcf_dataframe(df, org)

            summ = utils.plot_vcf_summary(df, show_plots=show_plots)

            df_overlaps = utils.check_for_overlaps(df)

            df_pse_pileup, num_snps_written, num_indels_written, overlap_positions = utils.create_pse_pileup_2(df,
                                                                                                         chrom, org,
                                                                                                         num_recs=num_recs)

            utils.plot_var_densities(chrom, org, base_density, num_snps_written, num_indels_written, show_plots=show_plots)

            utils.output_pse_pileup(df_pse_pileup, out_pse_full_name)

            utils.output_vcf_sample_only(df, comments_1, org, out_vcf_full_name, reduce_alts=True)

            print(' ')
            print('All steps complete!')

    def handle(self, chrom, strain, **options):
        '''The main entry point for the Django management command.

        '''

        if options['input_file'] is None:
            input_file = self.assemble_default_input_file(chrom,strain,'ALL')
            self.stdout.write('No input file specified. Using default: ' + input_file)
        else:
            input_file = options['input_file']


        input_vcf_folder = os.path.dirname(input_file)

        output_pse_file = self.assemble_default_output_pse_file(chrom,strain,options['output_folder'] )
        output_vcf_file = self.assemble_default_output_vcf_file(chrom,strain,'ALL_trimmed',input_vcf_folder) # output trimmed vcf  in same  folder as input vcf

        self.stdout.write(' ')
        self.stdout.write(self.style.SUCCESS('Input VCF file: ' + input_file))
        self.stdout.write(self.style.SUCCESS('Output trimmed VCF file ' + output_vcf_file))
        self.stdout.write(self.style.SUCCESS('Output PSE file ' + output_pse_file))

        self.stdout.write(' num_recs: ' + 'None' if options['num_recs'] is None else options['num_recs'])

        # self.process_vcf_all_steps('ALL', input_file, None,strain,chrom, output_pse_file,
        #                       output_vcf_file, file_type_2=None, file_name_2=None, num_recs=int(options['num_recs']),
        #                       base_density=100000,
        #                       show_plots=True)

        num_recs = None if options['num_recs'] is None else int(options['num_recs'])
        utils.process_vcf_quick('ALL', input_file, None,strain,chrom, output_pse_file,
                              output_vcf_file, num_recs=num_recs,
                              base_density=100000,
                              show_plots=True)

        self.stdout.write(self.style.SUCCESS('VCF conversion complete. Chrom: ' +  chrom + ' Strain: ' + strain))

