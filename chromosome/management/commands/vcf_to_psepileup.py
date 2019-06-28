'''A custom Django administrative command for importing chromosome data.

This command is intended to be used through Django's standard "management"
command interface, e.g.:

  # ./manage.py vcf_to_psepileup <file_to_convert>

<file_to_convert> should be a standard VCF file

'''

from django.core.management.base import BaseCommand
from optparse import make_option
import pandas as pd
import sys
#from chromosome.models import ChromosomeImporter, ChromosomeBatchImportProcess
#from django.db import connection, transaction
#import os
#import django.utils.timezone


class Command(BaseCommand):
    '''A custom command to convert VCF to psepileup format'''

    help = 'Converts vcf file to custom Noor lab psepileup format ready for import into Pseudobase.'
    args = '<path to VCF file>'

    option_list = BaseCommand.option_list + (
        make_option('-f','--output_folder',
                    dest='output_folder',
                    default='raw_data/chromosome/pending_import/',
                    help='output file folder'),
    )  + (
        make_option('-s', '--strain',
                    dest='strain',
                    default='strain',
                    help='strain'),

    )

    def find_depth(self,info):


        for item in info:
            item_split = item.split('=')
            # print ('item split 0: ',item_split[0])
            if item_split[0] == 'DP':
                # print ('returning item split 1: ',item_split[1])
                return item_split[1]
        return 'Q'


    def process_var(self,ref, alt, index, pos, debug=False):
        if (len(ref) == 1) and (len(alt) == 1):
            return alt, 0, 'S'  # snp
        elif (len(ref) > len(alt)):

            if len(ref) == 2 and len(alt) == 1:
                if debug:
                    print ('\nsingle del', ref, alt, index, pos)
                return 'D', 1, 'D'
            else:
                if debug:
                    print('\ndel with mult chars in vcf: ', ref, alt, index, pos)
                if (len(ref) > len(alt) + 1):
                    print('\nMulti del more than one!!!!. Not catered for', ref, alt, index, pos)
                return 'D', 1, 'D'

        elif (len(ref) == len(alt)):
            print('\nequal length var: ', ref, alt, index, pos)
            return '=', 0, 'E'
        else:  # insertion

            if len(ref) == 1 and len(alt) == 2:
                if debug:
                    print('\nsingle insert', ref, alt, index, pos)
                return alt[0] + ' ' + alt[1], 0, 'I'
            else:
                if debug:
                    print('\nmulti ins: ', ref, alt, index, pos)
                inserted_bases = alt[1:1 + len(alt) - len(ref)]
                return ref[0] + ' ' + inserted_bases, 0, 'I'


    def read_vcf_file(self,vcf_file_name):

        self.stdout.write('Reading VCF file: ' + vcf_file_name)
        rec_count = 0
        head = None
        comment_lines = []
        lines = []
        with open(vcf_file_name, 'r') as vcf_file:
            for i, line in enumerate(vcf_file):
                line = line.rstrip()
                rec_count += 1

                if line[:6] == '#CHROM':
                    head = line[1:].split('\t')
                    #print('head line: ', line)
                    comment_lines.append(line)
                    continue

                if line[:2] == '##':
                    comment_lines.append(line)
                    continue

                lines.append(line.split('\t'))

        self.stdout.write('Records read: ' + str(rec_count))

        df = pd.DataFrame(lines, columns=head)
        return df


    def process_vcf(self,df,options):

        sys.stdout.write('Converting VCF file ')
        ignore_next = False

        pse_pileup_list = []

        num_recs = df.shape[0]
        progress = num_recs // 20

        for index, row in df.iterrows():

            type = ''

            #if index % 50000 == 0:
            if index % progress == 0:
                sys.stdout.write('.')
                sys.stdout.flush()
                #print('\r', 'Processing VCF record: ', index, ' / ', df.shape[0], end='')
                #print('Processing VCF record: ' +  str(index) +  ' / ' + str(df.shape[0]))

            if ignore_next:
                ignore_next = False
                continue

            pse_pileup_line = ['']
            pse_pileup_line.append(row['CHROM'])
            pse_pileup_line.append(options['strain'])
            pos = str(row['POS'])
            vcf_info = row['INFO'].split(';')
            depth = self.find_depth(vcf_info)

            alts = row['ALT'].split(',')

            offset = 0

            if len(alts) == 1:
                if alts[0] == '<*>':
                    bases = row['REF']
                else:
                    bases, offset, type = self.process_var(row['REF'], alts[0], index, pos, debug=False)


            elif len(alts) == 2:
                if alts[1] == '<*>':
                    bases, offset, type = self.process_var(row['REF'], alts[0], index, pos, debug=False)

                else:
                    print('\nunexpected second alt. Terminating ', alts, ' index: ', index)
                    break

            elif len(alts) > 2:
                print('\nunexpected number of alts. Terminating. ', alts, ' index: ', index)
                break

            if type == 'E':
                print('\nUnexpected vcf var encountered - terminating')
                break

            pos = str(int(pos) + offset)
            if bases[0] == 'N':
                depth = 'N'
            bases_info = pos + ' ' + depth + ' ' + bases
            pse_pileup_line.append(bases_info)

            ignore_next = False

            if type == 'I':
                pse_pileup_list.pop()
            elif type == 'D':
                ignore_next = True

            pse_pileup_list.append(pse_pileup_line)

        df_pse_pileup = pd.DataFrame(pse_pileup_list, columns=['Blank', 'Chrom', 'Org', 'Base info'])

        #print('\npse pileup shape: ', df_pse_pileup.shape)

        sys.stdout.write('\n')
        sys.stdout.flush()

        return df_pse_pileup


    def get_chrom(self,df_pse_pileup):
        return df_pse_pileup.iloc[0]['Chrom']

    def output_psepileup(self,df_pse_pileup,options):
        out_ext = '.psepileup'

        full_output_name = options['output_folder'] + self.get_chrom(df_pse_pileup) + '_' + options['strain']  + out_ext

        self.stdout.write('Outputting:  ' + full_output_name)
        df_pse_pileup.to_csv(full_output_name, index=False, header=False, sep='\t')


    def convert_vcf_file(self,vcf_file_name,options):
        df = self.read_vcf_file(vcf_file_name)
        df_pse_pileup = self.process_vcf(df,options)
        self.output_psepileup(df_pse_pileup,options)




    def handle(self, vcf_file_name, **options):
        '''The main entry point for the Django management command.

        '''

        try:
            self.convert_vcf_file(vcf_file_name,options)
            self.stdout.write(self.style.SUCCESS('VCF conversion complete. In: ' + vcf_file_name + ' out folder: ' + options['output_folder']))
        except:
            raise








