'''A custom Django administrative command for merging two VCF files (typically SNP and INDEL).

This command is intended to be used through Django's standard "management"
command interface, e.g.:

  # ./manage.py vcf_merge <chrom strain>


'''

from django.core.management.base import BaseCommand
from django.conf import settings
from optparse import make_option
import os

import gzip
#from analyse_new_vcf import read_vcfs

import pandas as pd
import sys
#from chromosome.models import ChromosomeImporter, ChromosomeBatchImportProcess
#from django.db import connection, transaction
#import os
#import django.utils.timezone


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

    def read_vcf(self,full_name, release=None, num_recs=None):
        rec_count = 0
        head = None
        comment_lines = []
        lines = []

        print('  Reading: ', full_name)
        # with open(in_full_name,'r',encoding='utf-8') as vcf_file:    #OLD
        #    with gzip.open(full_name,'r') as vcf_file:                 #NEW
        vcf_file = gzip.open(full_name, 'r')
        for i, line in enumerate(vcf_file):

            if (num_recs is None):
                pass
            else:
                if len(lines) > num_recs:
                    break

            if i % 500000 == 0:
                print('    Reading VCF record ', i)
            # if i > 5000:
            #    break
            line = line.decode('utf-8').rstrip()  # NEW
            # line = line.rstrip()                    #OLD
            rec_count += 1

            if line[:6] == '#CHROM':
                head = line[1:].split('\t')
                if release is None:
                    pass
                else:
                    head[-1] = head[-1] + '_' + release
                # print('  head line: ',line)
                comment_lines.append(line)
                continue

            if line[:2] == '##':
                comment_lines.append(line)
                continue

            lines.append(line.split('\t'))

        vcf_file.close()
        print('    Reading complete')
        df = pd.DataFrame(lines, columns=head)
        # df["POS"] = pd.to_numeric(df["POS"])
        df["POS"] = df["POS"].astype(int)

        if num_recs is None:
            pass
        else:
            df = df[:num_recs]
        return df, comment_lines

    def read_vcfs(self,file_type_1, file_name_1, release, file_type_2=None, file_name_2=None, num_recs=None):

        print('Step 1 - Read source VCF file(s)...')

        df_1, comments_1 = self.read_vcf(file_name_1, release, num_recs=num_recs)

        print('    df_1 shape: ', df_1.shape)
        df_1['source'] = file_type_1
        # df_1.head()

        if file_type_2 is None:
            df = df_1.copy()
            comments_2 = None
        else:
            df_2, comments_2 = self.read_vcf(file_name_2, release, num_recs=num_recs)
            print('    df_2 shape: ', df_2.shape)
            df_2['source'] = file_type_2

            print('  Merging..')
            df = self.merge_vcf_dataframes(df_1, df_2)

            print('  Both shape: ', df.shape)

        return df, comments_1, comments_2

    def merge_vcf_dataframes(self,df1, df2):
        df = df1.append(df2, ignore_index=True)
        df = df.sort(['POS']) #df.sort_values(by='POS')
        df = df.reset_index(drop=True)
        return df

    def merge_vcfs(self,file_name_1, file_name_2, out_file_name, num_recs=None):
        df, comm_1, comm_2 = self.read_vcfs('SNP', file_name_1, release=None, file_type_2='INDEL', file_name_2=file_name_2,
                                       num_recs=num_recs)
        df_out_vcf = df.drop(['source'], axis=1)
        print('  Merge complete. Merged df shape: ', df_out_vcf.shape)

        print('  Converting df to list..')
        out_vcf_list = df_out_vcf.values.tolist()

        out_comments_str = '\n'.join(comm_1)

        print('  Ensuring all fields are str..')
        out_vcf_list = [[str(x) for x in entry] for entry in out_vcf_list]

        print('  Converting list to string..')
        out_vcf_str = '\n'.join(['\t'.join(x) for x in out_vcf_list])

        out_str = '\n'.join([out_comments_str, out_vcf_str])

        print('  Writing output file gzip..')

        #with gzip.open(out_file_name, "wb") as gzip_file:  # Not avail in Python 2.6
        #    gzip_file.write(out_str.encode('utf-8'))
        gzip_file = gzip.open(out_file_name,"wb")
        gzip_file.write(out_str.encode('utf-8'))

        print('  Complete')
        return df_out_vcf, comm_1, comm_2

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

        self.merge_vcfs(input_file_1,input_file_2,output_file)

        self.stdout.write(self.style.SUCCESS('VCF merge complete. Chrom: ' +  chrom + ' Strain: ' + strain))

