from __future__ import print_function # cater for printing on same line, ie with end=, on python < 3

#import matplotlib.pyplot as plt
#import numpy as np
import gzip
#import pandas as pd

'''
 VCF Analysis and Conversion routines 
'''

def read_vcf(full_name, release=None, num_recs=None):
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


def read_vcfs(file_type_1, file_name_1, release, file_type_2=None, file_name_2=None, num_recs=None):
    print('Step 1 - Read source VCF file(s)...')

    df_1, comments_1 = read_vcf(file_name_1, release, num_recs=num_recs)

    print('    df_1 shape: ', df_1.shape)
    df_1['source'] = file_type_1
    # df_1.head()

    if file_type_2 is None:
        df = df_1.copy()
        comments_2 = None
    else:
        df_2, comments_2 = read_vcf(file_name_2, release, num_recs=num_recs)
        print('    df_2 shape: ', df_2.shape)
        df_2['source'] = file_type_2

        print('  Merging..')
        df = merge_vcf_dataframes(df_1, df_2)

        print('  Both shape: ', df.shape)

    return df, comments_1, comments_2


def merge_vcf_dataframes(df1, df2):
    df = df1.append(df2, ignore_index=True)
    df = df.sort(['POS'])  # df.sort_values(by='POS')
    df = df.reset_index(drop=True)
    return df


def merge_vcfs(file_name_1, file_name_2, out_file_name, num_recs=None):
    df, comm_1, comm_2 = read_vcfs('SNP', file_name_1, release=None, file_type_2='INDEL', file_name_2=file_name_2,
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

    # with gzip.open(out_file_name, "wb") as gzip_file:  # Not avail in Python 2.6
    #    gzip_file.write(out_str.encode('utf-8'))
    gzip_file = gzip.open(out_file_name, "wb")
    gzip_file.write(out_str.encode('utf-8'))

    print('  Complete')
    return df_out_vcf, comm_1, comm_2


class VCFRecord:

    vcf_types = ['Filtered', 'Uncalled', 'Hom Ref', 'Het Ref', 'Hom Alt', 'Het Alt', '*', 'SNP', 'INDEL', 'Insertion',
             'Deletion']

    def __init__(self,line):

        self.CHROM,self.POS,self.ID,self.REF,self.ALT,self.QUAL,self.FILTER,self.INFO,self.FORMAT,self.SAMPLE= line.split('\t')[:10]

        self.alts =  self.ALT.split(',')

        self.parse_format()

        self.parse_gens()

    def parse_format(self):

        format_types = self.FORMAT.split(':')
        self.gen_ind = format_types.index('GT')
        self.ad_ind = format_types.index('AD')

        strain_info_list = self.SAMPLE.split(':')
        self.gens = [None if x == '.' else int(x) for x in strain_info_list[self.gen_ind].split('/')]
        self.ads = [int(x) for x in strain_info_list[self.ad_ind].split(',')]

    def parse_gens(self):
        try:
            self.gen_1 = self.gens[0]
            self.gen_2 = self.gens[1]
        except:
            print('gens is not a list: ', self.gens)
            raise

    def passed_filter(self):
        return self.FILTER == 'PASS'

    def is_homo_ref(self):
        return (self.gen_1 == 0) and (self.gen_2 == 0)

    def is_uncalled(self):
        return self.gen_1 is None and self.gen_2 is None

    def is_homo_alt(self):
        if self.is_uncalled():
            return False
        else:
            return (self.gen_1 == self.gen_2)  and (self.gen_1 > 0)

    @staticmethod
    def tot_summary_flags_to_meta_data(tot_summary_flags):
        meta_data = {}
        for i,vcf_type in enumerate(VCFRecord.vcf_types):
            meta_data[vcf_type] = tot_summary_flags[i]
        return meta_data

    def summary_flags(self):
        summary_flags = [0 for i in range(len(self.vcf_types))]

        var_type,var_bases,read_depth = self.var_type()

        if var_type == 'F':
           summary_flags[0] = 1

        else:
            if var_type == 'U':
               summary_flags[1] = 1

            if self.is_homo_ref():
                summary_flags[2] = 1

            if self.is_het() and (var_type == 'R'):
                summary_flags[3] = 1

            if self.is_homo_alt():
                summary_flags[4] = 1

            if self.is_het() and not (var_type == 'R'):
                summary_flags[5] = 1

            if var_type == '*':
                summary_flags[6] = 1

            if var_type == 'S':
                summary_flags[7] = 1

            if var_type == 'I' or var_type == 'D':
                summary_flags[8] = 1

            if var_type == 'I':
                summary_flags[9] = 1

            if var_type == 'D':
                summary_flags[10] = 1


        return summary_flags



    def determine_indel(self,called_bases):
        indel_type = None
        indel_bases = None

        if len(self.REF) > len(called_bases):
            indel_type = 'D'
            indel_bases = self.REF[1:len(self.REF) - len(called_bases) + 1]
        else:
            indel_type = 'I'
            indel_bases = called_bases[0] + called_bases[1:len(called_bases) - len(self.REF) + 1]

        return indel_type,indel_bases




    def var_type(self):
        if self.passed_filter():
            if self.is_uncalled():
                return 'U',None,None
            elif self.is_homo_ref():
                called_bases, read_depth = self.called_bases()
                return 'R',self.REF[0],read_depth
            elif self.is_homo_alt() or self.is_het():
                called_bases,read_depth = self.called_bases()
                if called_bases == '*':
                    return '*',called_bases,read_depth
                elif called_bases == 'R':
                    # Het but most abundant is ref
                    return 'R',self.REF[0],read_depth
                elif len(self.REF) == 1 and len(called_bases) == 1:
                    return 'S',called_bases,read_depth
                else:
                    var_type,var_bases = self.determine_indel(called_bases)
                    return var_type,var_bases,read_depth

            else:
                print('Unknown var type!! ' + str(self.POS))
                return None,None,None
        else:
            return 'F',None,None

    def is_het_both_alt(self):
        if self.is_het():
             if self.gen_1 == 0 or self.gen_2 == 0:
                 return False
             else:
                 return True
        else:
            return False


    def is_het(self):
        return self.gen_1 != self.gen_2

    def most_abundant_read(self):
        reads_1 = self.ads[self.gen_1]
        reads_2 = self.ads[self.gen_2]
        max_gen = self.gen_2 if reads_2 > reads_1 else self.gen_1

        if max_gen == 0:
            return 'R',self.ads[0]
        else:
            return self.alts[max_gen - 1],self.ads[max_gen]

    def called_bases(self):
        if self.is_uncalled():
            return None,None
        elif self.is_homo_ref():
            return 'R',self.ads[0]
        elif self.is_homo_alt():
            return self.alts[self.gen_1 -1],self.ads[self.gen_1]
        elif self.is_het():
            return  self.most_abundant_read()

    def __str__(self):
        return ' '.join([self.POS,self.REF,self.ALT,str(self.summary_flags()),self.FORMAT,self.SAMPLE,str(self.gens),str(self.ads),str(self.var_type()),
                         'HR' if self.is_homo_ref() else '-','HA' if self.is_homo_alt() else '-','U' if self.is_uncalled() else '-','HE' if self.is_het() else '-',str(self.called_bases())])
