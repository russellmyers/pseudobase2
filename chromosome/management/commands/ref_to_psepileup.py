'''A custom Django administrative command for importing chromosome data.

This command is intended to be used through Django's standard "management"
command interface, e.g.:

  # ./manage.py ref_to_psepileup <reference fasta file_to_convert>

<file_to_convert> should be a standard fasta file representing all chromosomes for the reference strain

'''

from django.core.management.base import BaseCommand
from django.conf import settings
from optparse import make_option
import gzip
from common.models import Chromosome
from common.models import StrainSymbol

import pandas as pd
import sys

class Command(BaseCommand):
    '''A custom command to convert Ref Fasta to psepileup format'''

    help = 'Converts reference fasta file to custom Noor lab psepileup format ready for import into Pseudobase.'
    args = '<path to ref fasta file>'

    option_list = BaseCommand.option_list + (
        make_option('-f','--output_folder',
                    dest='output_folder',
                    default=settings.PSEUDOBASE_CHROMOSOME_RAW_DATA_PENDING_PREFIX,
                    help='output file folder'),
    )

    def create_ref_pse_pileup(self, fa, chrom, org, num_recs=None):
        pse_pileup_lines = []
        fa_str = ''.join(fa[1:])
        print('fa str len: ', len(fa_str))

        for i, base in enumerate(fa_str):
            if num_recs is None:
                pass
            else:
                if i > num_recs:
                    break
            line = '\t'.join([chrom, org, str(i + 1), base])
            pse_pileup_lines.append(line)

        return pse_pileup_lines

    def output_psepileup(self, pse_pileup_lines, chrom, strain, options):
        out_ext = '.psepileup'

        full_output_name = options['output_folder'] + chrom + '_' + strain + out_ext

        self.stdout.write('  Outputting:  ' + full_output_name)

        pse_pileup_str = '\n'.join(pse_pileup_lines)
        out_file = open(full_output_name, "w")  # write mode
        out_file.write(pse_pileup_str)
        out_file.close()

    def create_ref_pse_pileup(self, fa, chrom, org, debug=False, num_recs=None):
        pse_pileup_lines = []
        fa_str = ''.join(fa[1:])
        # print('fa str len: ', len(fa_str))

        for i, base in enumerate(fa_str):
            if debug and (i % 1000000 == 0):
                self.stdout.write('  Creating base position: ' + str(i))
            if num_recs is None:
                pass
            else:
                if i > num_recs:
                    break
            line = '\t'.join([chrom, org, str(i + 1), base])
            pse_pileup_lines.append(line)

        return pse_pileup_lines

    def get_seq(self, ref_file_name, chrom, debug=False):

        self.stdout.write('Converting Chromosome: ' + chrom)

        in_fasta = False

        chrom_len = 0

        fasta_seq = []

        fin = gzip.open(ref_file_name, 'r')
        # with gzip.open(ref_file_name, 'r') as fin:
        for i, line in enumerate(fin):
            if i % 100000 == 0:
                if debug:
                    self.stdout.write('i: ' + str(i) + ' line: ' + line.decode('utf-8')[:150])

            line_str = line.decode('utf-8')
            if line_str[0] == '>':
                if debug:
                    print ('header: ' + str(i) + ' ' + line_str)

                if in_fasta:
                    return fasta_seq, chrom_len

                if line_str[1:1 + len(chrom)] == chrom:
                    fasta_seq.append(line_str.rstrip())
                    in_fasta = True
            else:
                if in_fasta:
                    fasta_line = line_str.rstrip()
                    fasta_seq.append(fasta_line)
                    chrom_len += len(fasta_line)

        return fasta_seq, chrom_len

    def get_ref_strain_symbol(self):
        try:
            strain_symbols = StrainSymbol.objects.filter(strain__is_reference=True)
            return str(strain_symbols[0].symbol)
        except:
            return 'Unknown'

    def get_chromosome_names(self):
        chromosomes = Chromosome.objects.all()
        return [chr.name for chr in chromosomes]

    def convert_ref_file(self,ref_file_name,options):
        chrom_names = self.get_chromosome_names()

        ref_symbol = self.get_ref_strain_symbol()
        self.stdout.write('ref strain symbol: ' + str(ref_symbol))

        for chrom in chrom_names:
            fasta_seq,chrom_len = self.get_seq(ref_file_name,chrom)
            lines = self.create_ref_pse_pileup(fasta_seq,chrom,ref_symbol,debug=True)
            self.output_psepileup(lines,chrom,ref_symbol,options=options)
            #self.stdout.write('lines: ' + str(lines[:2]))
            self.stdout.write('Chromosome: ' + str(chrom) + ' conversion complete. Sequence len: ' + str(chrom_len))

    def handle(self, ref_file_name, **options):
        '''The main entry point for the Django management command.

        '''

        try:
            self.convert_ref_file(ref_file_name,options)
            self.stdout.write(self.style.SUCCESS('Ref Fasta conversion complete. In: ' + ref_file_name + ' out folder: ' + options['output_folder']))
        except:
            raise








