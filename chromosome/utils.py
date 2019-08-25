from __future__ import print_function # cater for printing on same line, ie with end=, on python < 3

import matplotlib.pyplot as plt
import numpy as np
import gzip
import pandas as pd

#from .models import ChromosomeBase


gt_hom_ref = 'R'
gt_het = 'H'
gt_hom_alt = 'A'
gt_uncalled = 'U'
gt_huh = '?'  # what the?


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


def vcf_duplicate_positions(df):
    print('')
    print('Step 2 - Check for duplicate positions...')

    dup = df[df.duplicated()]

    print('\n  ', dup.shape[0], ' duplicate positions found')

    return dup


def find_depth(info):
    for item in info:
        item_split = item.split('=')
        # print ('item split 0: ',item_split[0])
        if item_split[0] == 'DP':
            # print ('returning item split 1: ',item_split[1])
            return item_split[1]
    return 'Q'


def find_het_alt_pos(gens, ads):
    # TODO  Replace with calling alt only if more abundant than ref)
    # If one of the alleles is reference, then call the other one
    # If both alleles are alt, then use the one with greater depth

    if (gens[0] == '0'):
        alt_pos = int(gens[1]) - 1

    elif (gens[1] == '0'):
        alt_pos = int(gens[0]) - 1

    else:
        if int(ads[int(gens[1])]) > int(ads[int(gens[0])]):
            alt_pos = int(gens[1]) - 1

        else:
            alt_pos = int(gens[0]) - 1

        if len(ads) >= 3 and (ads[0] == '2' and ads[1] == '21' and ads[2] == '3'):
            # print('genads: ',gens,ads,alt_pos,int(ads[alt_pos + 1]))
            pass

    return alt_pos, int(ads[alt_pos + 1])  # ads also includes ref, so add 1


def check_genotype(row, org):
    global dots_found
    global non_homos_found
    global homos_greater_than_1_found
    global num_homo_zero

    extra_gen_type = ''  # additional info about genotype info

    format_types = row['FORMAT'].split(':')
    gen_ind = format_types.index('GT')
    ad_ind = format_types.index('AD')
    strain_info_list = row[org].split(':')
    gens = strain_info_list[gen_ind].split('/')
    ads = strain_info_list[ad_ind].split(',')

    use_alt_pos = 0

    try:
        gen_1 = gens[0]
        gen_2 = gens[1]
    except:
        print('gens is not a list: ', gens)
        raise

    if (gen_1 == gen_2) and (gen_1 == '0'):
        # num_homo_zero +=1
        gen_type = gt_hom_ref
    elif (gen_1 == gen_2) and (gen_1 == '.'):
        # dots_found.append(row)
        gen_type = gt_uncalled
        extra_gen_type = '.'

        # print('. found: ',row['POS'],gens,ads)
    elif (gen_1 == gen_2):
        gen_type = gt_hom_alt
        if gen_1 != '1':
            # homos_greater_than_1_found.append(row)
            extra_gen_type = '>'
        use_alt_pos = int(gen_1) - 1

    elif len(row[org]) == 0:
        # dots_found.append(row)
        gen_type = gt_uncalled
        extra_gen_type = 'B'  # blank
    elif row[org][0] == ' ':
        # dots_found.append(row)
        gen_type = gt_uncalled
        extra_gen_type = 'B'  # blank

    else:
        # non_homos_found.append(row)
        gen_type = gt_het
        use_alt_pos, alt_depth = find_het_alt_pos(gens, ads)
    # print('Non homo found: ',row['POS'],gens,ads)

    return gen_type, extra_gen_type, gens, ads, use_alt_pos




def process_var_record(row, org, only_include_pass_records=False, debug=False):
    global alt_star_called

    if only_include_pass_records:
        if row['FILTER'] == 'PASS':
            passed = True
        else:
            passed = False
    else:
        passed = True

    alts = row['ALT'].split(',')
    ref = row['REF']

    gen_type, extra_gen_type, gens, ads, use_alt_pos = check_genotype(row, org)

    if not passed:
        return 'P', gen_type, extra_gen_type, ref[0]

    var_type = ''
    ref_bases = ref
    bases = ref  # ref[0]
    indel_bases = ''

    alt_num = ' '

    if (gen_type == gt_hom_alt) or (gen_type == gt_het):
        if (alts[use_alt_pos] == '*'):
            var_type = '*'
        else:
            if (len(ref) == 1) and (len(alts[use_alt_pos]) == 1):
                var_type = 'S'  # SNP
                bases = alts[use_alt_pos]
            else:
                # print('something else encountered. ref: ',ref,' alts: ',alts, ' pos: ', row['POS'])
                # print('E type - ref not equal 1. Need to cater for this: ',ref, ' pos: ',row['POS'])
                var_type = 'L'  # INDEL
                bases = alts[use_alt_pos]  # TODO fix this for deletions
                extra_gen_type = 'D' if len(ref) > len(alts[use_alt_pos]) else 'I'
                if extra_gen_type == 'D':
                    indel_bases = ref[1:len(ref) - len(alts[use_alt_pos]) + 1]
                else:
                    indel_bases = alts[use_alt_pos][1:len(alts[use_alt_pos]) - len(ref) + 1]

        alt_num = str(use_alt_pos + 1)

    elif gen_type == gt_hom_ref:
        var_type = 'R'  # ref
    #     elif gen_type == gt_het:
    #          var_type = 'H'
    else:
        var_type = 'U'  # uncalled

    return var_type, gen_type, extra_gen_type, bases, ref_bases, indel_bases, alt_num


def analyse_vcf_dataframe(df, org, debug=False, only_include_pass_records=False):
    print(' ')
    print('Step 3 - Analyse VCF dataframe...')

    df_parsed = df.copy()
    alt_nums = []
    var_types = []
    gen_types = []
    extra_gen_types = []
    ref_bases_list = []
    bases_list = []
    indel_bases_list = []

    for index, row in df.iterrows():

        if index % 10000 == 0:
            print('\r', ' Processing record: ', index, '/', df.shape[0], end='')

        var_type, gen_type, extra_gen_type, bases, ref_bases, indel_bases, alt_num = process_var_record(row, org,
                                                                                                        only_include_pass_records,
                                                                                                        debug)
        var_types.append(var_type)
        gen_types.append(gen_type)
        extra_gen_types.append(extra_gen_type)
        ref_bases_list.append(ref_bases)
        bases_list.append(bases)
        indel_bases_list.append(indel_bases)
        alt_nums.append(alt_num)

    df_parsed['var_type'] = var_types
    df_parsed['gen_type'] = gen_types
    df_parsed['alt_num'] = alt_nums
    df_parsed['extra_gen_type'] = extra_gen_types
    df_parsed['ref_bases'] = ref_bases_list
    df_parsed['bases'] = bases_list
    df_parsed['indel_bases'] = indel_bases_list

    print('\n  Processing complete')

    return df_parsed


def plot_vcf_summary(df, show_plots=False):
    print(' ')
    print('Step 4 - Summarise and plot...')
    df_homo_ref = df[df['var_type'] == 'R']
    df_alt_star = df[df['var_type'] == '*']
    df_snp_to_write = df[df['var_type'] == 'S']
    df_indel_to_write = df[df['var_type'] == 'L']
    df_het = df[df['gen_type'] == gt_het]
    df_uncalled = df[df['var_type'] == 'U']
    summ = [df_homo_ref.shape[0], df_het.shape[0], df_alt_star.shape[0], df_uncalled.shape[0], df_snp_to_write.shape[0],
            df_indel_to_write.shape[0]]
    if show_plots:
        x_labs = ['Hom ref', 'Het', 'Alt*', 'Uncalled', 'snp write', 'indel write']
        x_vals = [x for x in range(len(x_labs))]
        plt.bar(x_vals, summ)
        plt.xticks(x_vals, x_labs)
        # plt.ion()
        plt.show()
    else:
        print('  Bypassing plot')

    print('  Summary: ', summ)

    return summ


def check_for_overlaps(df):
    print(' ')
    print('Step 5 - Check for overlaps...')

    df_snp_indel_to_write = df[(df['var_type'] == 'S') | (df['var_type'] == 'L')]
    overlaps = []

    prev_pos = -1000000
    prev_ref_len = -1
    curr_pos = -1
    curr_ref_len = -1
    prev_row = None
    prev_extra_gen_type = ''
    curr_indel_bases = ''

    i = 0
    for index, row in df_snp_indel_to_write.iterrows():

        #    if i > 10000:
        #        break

        # print('\nrow: ',index,'var type: ',row['var_type'])
        if i % 10000 == 0:
            print('\r', '  Processing record: ', i, '/', df_snp_indel_to_write.shape[0], end='')
        #    if (row['var_type'] == 'S') or (row['var_type'] == 'L'):

        curr_pos = row['POS']
        curr_ref_len = len(row['ref_bases'])
        curr_indel_bases = row['indel_bases']
        curr_extra_gen_type = row['extra_gen_type']
        # print('\nprev: ',prev_pos,prev_ref_len,'curr: ',curr_pos,curr_ref_len)

        if (prev_extra_gen_type == 'D') and (prev_pos + (len(prev_indel_bases)) >= curr_pos):
            overlaps.append(prev_row)
            overlaps.append(row)

        prev_pos = curr_pos
        prev_ref_len = curr_ref_len
        prev_indel_bases = curr_indel_bases[:]
        prev_extra_gen_type = curr_extra_gen_type
        prev_row = row.copy()
        i += 1

    print('\n   Processing complete')
    print('  overlaps found: ', len(overlaps))

    df_overlaps = pd.DataFrame(overlaps)
    return df_overlaps


def get_ref_chrom(chrom, num_recs=None):

    ref_chrom_seq = ChromosomeBase.objects.get_all_ref_bases(chrom)
    if ref_chrom_seq is None:
        raise Exception('Reference sequence for chrom: ' + chrom  +' not found. Please run "ref_to_psepileup" command and import reference sequences first.')

    if num_recs is None:
        pass
    else:
        ref_chrom_seq = ref_chrom_seq[:num_recs]

    # f = open(ref_file_name, 'r')
    # content = f.read()
    # f.close()
    #
    # ref_chrom_seq = ''
    # num_chrom_lines = 0
    #
    # lines = content.split('\n')
    # in_ref_chrom = True
    #
    # print('  Reading ref chrom')
    # for line in lines:
    #     if line[0] == '>':
    #
    #         ref_chrom_name = line[1:].split(' ')[0]
    #
    #         if ref_chrom_name == chrom:
    #             print('    head: ', line[:40], ' chr: ', ref_chrom_name)
    #             in_ref_chrom = True
    #         else:
    #             in_ref_chrom = False
    #     else:
    #         if in_ref_chrom:
    #             ref_chrom_seq += line
    #             num_chrom_lines += 1
    #
    #             if num_recs is None:
    #                 pass
    #             else:
    #                 if num_recs < num_chrom_lines:
    #                     break
    #             if num_chrom_lines % 100000 == 0:
    #                 print('\r', '      Reading Chrom: ', chrom, '. Lines processed: ', num_chrom_lines, end='')

    return ref_chrom_seq


def get_vcf_pos_for_index(df, index):
    if index >= df.shape[0]:
        return None

    return int(df.iloc[index].POS)



def create_psepileup_skeleton_from_ref(chrom, org, num_recs=None):
    ref_chrom_seq = get_ref_chrom(chrom, num_recs)
    print('  Length ref chrom seq: ', len(ref_chrom_seq))

    pse_pileup_list = []
    print('  Creating psepileup skeleton')

    for i, ref_seq_base in enumerate(ref_chrom_seq):
        if num_recs is None:
            pass
        else:
            if i >= num_recs:
                break

        pse_pileup_list.append(['', chrom, org, str(i + 1) + ' 0 ' + ref_seq_base])
        if i % 500000 == 0:
            print('\r', '    Processing: ', i, end='')

    return pse_pileup_list


def create_pse_pileup_2(df, chrom, org, num_recs=None, create_analysis_dataframes=False):
    print(' ')
    print('Step 6 - Parse ref and create pse pileup..')
    only_include_pass_records = True

    pse_pileup_list = []

    if create_analysis_dataframes:
        skipped_vars = []
        non_passed_vars = []
        vars_written = []

    num_skipped_vars = 0
    num_non_passed_vars = 0
    num_vars_written = 0

    num_uncalled = 0
    num_het = 0
    num_alt_star_called = 0
    num_homo_zero = 0  # Number of homo ref calls
    num_called_but_not_passed = 0

    base_density = 100000

    # for index,row in df.iterrows():
    ref_pos = 0

    curr_window_num_snps_written = 0  # num snps in current base_density window
    curr_window_num_indels_written = 0  # num snps in current base_density window

    tot_snps_written = 0
    tot_indels_written = 0

    # vcf_index = 0
    # vcf_pos = get_vcf_pos_for_index(df,vcf_index)
    # print('  vcf pos first: ',vcf_pos)

    overlap_positions = []

    vcf_pos_col = 2
    pse_base_info_col = 3
    vcf_filter_col = 7
    vcf_info_col = 8
    vcf_var_type_col = 12
    vcf_gen_type_col = 13
    vcf_extra_gen_type_col = 15
    vcf_bases_col = 17
    vcf_indel_bases_col = 18

    del_bases = []
    del_depth = -1

    overlaps = []

    print(' ')

    pse_pileup_list = create_psepileup_skeleton_from_ref(chrom, org, num_recs=num_recs)

    num_density_buckets = len(pse_pileup_list) // base_density + 1
    num_snps_written = [0 for i in range(num_density_buckets)]  # Number of SNPs per base_density bases
    num_indels_written = [0 for i in range(num_density_buckets)]  # # Number of INDELs per base_density bases

    print('\n  Applying VCF vars')
    # i = 0
    # for vcf_index,row in df.iterrows():
    for i, row in enumerate(df.itertuples()):

        if i % 100000 == 0:
            print('\r', '    Proc var: ', i, 'wrote: ', num_vars_written, 'skip: ', num_skipped_vars, 'hom0: ',
                  num_homo_zero, 'dots: ', num_uncalled, 'alt*: ', num_alt_star_called, 'called but not passed: ',
                  num_called_but_not_passed, 'het: ', num_het, end='')
        ref_pos += 1  # 1-based

        pse_index = int(row[vcf_pos_col]) - 1
        pos = str(row[vcf_pos_col])

        if num_recs is None:
            pass
        elif pse_index >= num_recs:
            print('\n    breaking at ', i, 'pse index: ', pse_index)
            break

        # if (i != 0) and (i % base_density == 0):
        #   num_snps_written.append(curr_window_num_snps_written)
        #   num_indels_written.append(curr_window_num_indels_written)
        #   curr_window_num_snps_written = 0
        #   curr_window_num_indels_written = 0

        i += 1
        type = ''

        # print('ref pos: ',ref_pos,'del bases: ',del_bases)
        #         if (len(del_bases) > 0) and (del_bases[0] == int(ref_pos)):
        #             #print('aha')
        #             # deletion
        #             #pse_pileup_line = ['']
        #             #pse_pileup_line.append(chrom) #   (row['CHROM'])
        #             #pse_pileup_line.append(org)
        #             pse_pileup_line = ['',chrom,org]
        #             pos = str(ref_pos)
        #             depth = del_depth
        #             bases = 'D'
        #             bases_info =  pos + ' ' + depth + ' ' + bases
        #             #print('bases info: ',bases_info)
        #             pse_pileup_line.append(bases_info)
        #             pse_pileup_list.append(pse_pileup_line)
        #             del_bases = del_bases[1:]

        #             del_this_base = True

        #         else:
        #             del_depth = -1

        # pse_pileup_line = ['']
        # pse_pileup_line.append(chrom) #   (row['CHROM'])
        # pse_pileup_line.append(org)
        # pse_pileup_line = ['',chrom,org]

        curr_base_info = pse_pileup_list[pse_index][pse_base_info_col].split(' ')

        if (row[vcf_var_type_col] == 'R') or (row[vcf_var_type_col] == 'U') or (row[vcf_var_type_col] == '*'):
            num_skipped_vars += 1
            if create_analysis_dataframes:
                skipped_vars.append(row)
            if row[vcf_var_type_col] == 'R':
                num_homo_zero += 1
            #             if row[vcf_var_type_col] == 'H':
            #                 num_het +=1
            if row[vcf_var_type_col] == 'U':
                num_uncalled += 1
            if row[vcf_var_type_col] == '*':
                num_alt_star_called += 1

            depth = '0'

            if row[vcf_var_type_col] == '*':
                pass  # don't write anything
            else:
                if curr_base_info[1] == '0':

                    if row[vcf_var_type_col] == 'U':
                        curr_base_info[2] = 'N'  # Not called
                    else:
                        vcf_info = row[vcf_info_col].split(';')
                        depth = find_depth(vcf_info)
                        curr_base_info[1] = str(depth)
                    pse_pileup_list[pse_index][pse_base_info_col] = ' '.join(curr_base_info)
            continue

        elif row[vcf_filter_col] != 'PASS':
            num_skipped_vars += 1
            if create_analysis_dataframes:
                skipped_vars.append(row)
            curr_base_info[2] = 'N'  # Not called
            pse_pileup_list[pse_index][pse_base_info_col] = ' '.join(curr_base_info)

            num_called_but_not_passed += 1

        elif (row[vcf_var_type_col] == 'L') or (row[vcf_var_type_col] == 'S'):
            num_vars_written += 1
            vcf_info = row[vcf_info_col].split(';')
            depth = find_depth(vcf_info)

            if create_analysis_dataframes:
                vars_written.append(row)

            if row[vcf_gen_type_col] == 'H':
                num_het += 1

        bases = row[vcf_bases_col]

        if (row[vcf_var_type_col] == 'S') or (row[vcf_extra_gen_type_col] == 'I'):

            if row[vcf_extra_gen_type_col] == 'I':
                bases_info = pos + ' ' + depth + ' ' + bases[0] + row[vcf_indel_bases_col]
            else:
                bases_info = pos + ' ' + depth + ' ' + bases
            pse_pileup_list[pse_index][pse_base_info_col] = bases_info
            if (row[vcf_var_type_col] == 'S'):
                curr_window_num_snps_written += 1
                tot_snps_written += 1
                num_snps_written[int(pos) // base_density] += 1
            else:
                curr_window_num_indels_written += 1
                num_indels_written[int(pos) // base_density] += 1
                tot_indels_written += 1

            if curr_base_info[1] == '0':
                pass
            else:
                overlap_positions.append(row[vcf_pos_col])
                # print('\n    writing and overlaps with prev: ',row['POS'])

        else:
            # print('1 before del: ',pos,depth,ref_chrom_seq[ref_pos - 1])
            curr_window_num_indels_written += 1
            num_indels_written[int(pos) // base_density] += 1
            tot_indels_written += 1
            for del_index in range(pse_index + 1, pse_index + 1 + len(row[vcf_indel_bases_col])):
                bases_info = str(del_index + 1) + ' ' + depth + ' ' + 'D'
                pse_pileup_list[del_index][pse_base_info_col] = bases_info

        # pse_pileup_list.append(pse_pileup_line)

    print('\n  Proc fin: ', ref_pos, 'vars: ', i, 'wrote: ', num_vars_written, 'skip: ', num_skipped_vars, 'hom0: ',
          num_homo_zero, 'dots: ', num_uncalled, 'alt*: ', num_alt_star_called, 'called but not passed: ',
          num_called_but_not_passed, 'het: ', num_het)

    print(' ')
    print('  Vars written: ', num_vars_written)
    print('  Total snps written: ', tot_snps_written)
    print('  Total indels written: ', tot_indels_written)
    # print('  Non passed vars: ',num_non_passed_vars)

    print(' ')
    print('  Skipped vars: ', num_skipped_vars)
    print('  Num zero homo ref: ', num_homo_zero)
    print('  Dots: ', num_uncalled)
    print('  alt * called: ', num_alt_star_called)
    print('  Called but not passed: ', num_called_but_not_passed)
    print(' ')
    print('  het: ', num_het)

    print('  Num overlaps: ', len(overlap_positions))

    print(' ')
    print('  VCF processing complete - creating pandas analysis dfs')

    if create_analysis_dataframes:
        df_skipped_vars = pd.DataFrame(skipped_vars)
        df_non_passed_vars = pd.DataFrame(non_passed_vars)
        df_vars_written = pd.DataFrame(vars_written)

    print('  Creating psepileup dataframe')

    df_pse_pileup = pd.DataFrame(pse_pileup_list, columns=['Blank', 'Chrom', 'Org', 'Base info'])
    return df_pse_pileup, num_snps_written, num_indels_written, overlap_positions


def plot_var_densities(chrom, org, base_density, num_snps_written, num_indels_written, show_plots=False):
    print(' ')
    print('Step 7 - Plot var densities...')

    snp_densities = [x / base_density for x in num_snps_written]
    x_vals = [x * base_density / 1000000 for x in range(1, len(num_snps_written) + 1)]

    if show_plots:
        plt.plot(x_vals, snp_densities)
        plt.title(chrom + "/" + org + " SNP densities (sampled per " + str(base_density) + " bases)")
        plt.xlabel("Base position MBs")
        plt.ylabel("SNP density");

        # plt.ion()
        plt.show()
    else:
        print('  Bypassing SNP density plot')

    # print('Total num ref bases: ',len(ref_chrom_seq))
    # print('Total num SNPS writte: ',tot_snps_written)
    # print('Overall average SNP density: ',tot_snps_written / len(ref_chrom_seq))

    indel_densities = [x / base_density for x in num_indels_written]
    x_vals = [x * base_density / 1000000 for x in range(1, len(num_indels_written) + 1)]

    if show_plots:
        plt.plot(x_vals, indel_densities)
        plt.title(chrom + "/" + org + " INDEL densities (sampled per " + str(base_density) + " bases)")
        plt.xlabel("Base position MBs")
        plt.ylabel("INDEL density");

        # plt.ion()
        plt.show()
    else:
        print('  Bypassing INDEL density plot')


def output_pse_pileup(df, file_name):
    print(' ')
    print('Step 8 - Output pse pileup file...')
    df.to_csv(file_name, index=False, header=False, sep='\t', compression='gzip')


def simplify_alts(row, org):
    new_row = pd.Series(row)

    if (row['var_type'] == 'U') or (row['gen_type'] == 'H'):
        return new_row

    use_alt_pos = int(row['alt_num']) - 1
    new_row['ALT'] = new_row['ALT'].split(',')[use_alt_pos]

    sample_data = row[org].split(':')
    sample_data[0] = '1/1'

    ads = sample_data[1].split(',')
    new_ads = [ads[0], ads[use_alt_pos + 1]]
    new_ads_str = ','.join(new_ads)
    sample_data[1] = new_ads_str

    new_row[org] = ':'.join(sample_data)

    return new_row


def output_vcf_sample_only(df, comments, org, file_name, reduce_alts=False):
    # TODO Make this work effectively (ie need to remove other alts which are not relevant etc)
    print(' ')
    print('Step 9 - Output vcf file with single sample(org) only...')

    df_snp_indel_to_write = df[(df['var_type'] == 'S') | (df['var_type'] == 'L') | (df['var_type'] == 'U')]

    if reduce_alts:
        df_snp_indel_to_write = df_snp_indel_to_write.apply(simplify_alts, org=org, axis=1)

    df_out_vcf = df_snp_indel_to_write.drop(
        ['source', 'var_type', 'gen_type', 'alt_num', 'extra_gen_type', 'ref_bases', 'bases', 'indel_bases'], axis=1)
    df_out_vcf.head()

    out_vcf_list = df_out_vcf.values.tolist()
    len(out_vcf_list)

    out_comments_str = '\n'.join(comments)

    # for entry in out_vcf_list:
    #    line = '\t'.join(str(x)) for x in entry

    out_vcf_list = [[str(x) for x in entry] for entry in out_vcf_list]

    out_vcf_str = '\n'.join(['\t'.join(x) for x in out_vcf_list])

    out_str = '\n'.join([out_comments_str, out_vcf_str])

    # with gzip.open(file_name, "wb") as text_file:
    text_file = gzip.open(file_name, "wb")
    text_file.write(out_str.encode('utf-8'))
    text_file.close()


def get_ref_seq_from_fasta(self, ref_file_name, chrom, debug=False):

    in_fasta = False

    chrom_len = 0

    fasta_seq = []

    header = ''

    fin = gzip.open(ref_file_name, 'r')
    for i, line in enumerate(fin):
        if i % 100000 == 0:
            if debug:
                self.stdout.write('i: ' + str(i) + ' line: ' + line.decode('utf-8')[:150])

        line_str = line.decode('utf-8')
        if line_str[0] == '>':

            if debug:
                print ('header: ' + str(i) + ' ' + line_str)

            if in_fasta:
                return fasta_seq, chrom_len,header

            if line_str[1:1 + len(chrom)] == chrom:
                fasta_seq.append(line_str.rstrip())
                in_fasta = True
                header = line_str
        else:
            if in_fasta:
                fasta_line = line_str.rstrip()
                fasta_seq.append(fasta_line)
                chrom_len += len(fasta_line)

    return fasta_seq, chrom_len,header

def get_ref_strain_symbol(self):
    try:
        strain_symbols = StrainSymbol.objects.filter(strain__is_reference=True)
        return str(strain_symbols[0].symbol)
    except:
        return 'Unknown'



class VCFRecord:



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


    def summary_flags(self):
        types = ['F','U','HR','HER','HA','HEA','*','S','L','I','D']
        summary_flags = [0 for i in range(len(types))]

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
            indel_bases = called_bases[1:len(called_bases) - len(self.REF) + 1]

        return indel_type,indel_bases




    def var_type(self):
        if self.passed_filter():
            if self.is_uncalled():
                return 'U',None,None
            elif self.is_homo_ref():
                called_bases, read_depth = self.called_bases()
                return 'R',self.REF,read_depth
            elif self.is_homo_alt() or self.is_het():
                called_bases,read_depth = self.called_bases()
                if called_bases == '*':
                    return '*',called_bases,read_depth
                elif called_bases == 'R':
                    # Het but most abundant is ref
                    return 'R',self.REF,read_depth
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
            return 'R',None
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

    def apply_snp(self,line,var_type,var_bases,read_depth):
        #0 pos
        #1 read depth
        #2 base
        #3 inserted bases
        bases_info = line[-1].split(' ')
        bases_info[1] = str(read_depth)
        bases_info[2] = var_bases
        line[-1] = ' '.join(bases_info)

    def apply_not_passed_or_uncalled(self,line,var_type,var_bases,read_depth):
        bases_info = line[-1].split(' ')
        bases_info[1] = 'N'
        bases_info[2] = 'N'
        line[-1] = ' '.join(bases_info)

    def apply_insertion(self, line, var_type, var_bases, read_depth):
        bases_info = line[-1].split(' ')
        bases_info[1] = str(read_depth)
        if len(bases_info) == 4:
         bases_info[3] = var_bases
        else:
         bases_info.append(var_bases)
        line[-1] = ' '.join(bases_info)


    def apply_deletion(self,line,var_type,var_bases,read_depth):
        bases_info = line[-1].split(' ')
        bases_info[1] = str(read_depth)
        bases_info[2] = 'D'
        line[-1] = ' '.join(bases_info)


    def apply_homo_ref(self,line,var_type,var_bases,read_depth):
        bases_info = line[-1].split(' ')
        bases_info[1] = str(read_depth)
        line[-1] = ' '.join(bases_info)

    def apply_to_pse_pileup_line(self,pse_ind,pse_pileup_list):

        var_type, var_bases, read_depth = self.var_type()

        line = pse_pileup_list[pse_ind]

        if not self.passed_filter() or (var_type == 'U'):
            # write N
            # print('F or U: ',self)
            self.apply_not_passed_or_uncalled(line,var_type,var_bases,read_depth)
        else:
            if var_type == '*':
                # Ignore
                #print('*: ', self)
                pass
            elif var_type == 'R':  # Homo ref or het called as reference
                # write read depth
                if self.is_het():
                    #print('RH: ', self)
                    pass

                self.apply_homo_ref(line,var_type,var_bases,read_depth)
            else:
                if self.is_homo_alt():
                    #print('HA S,L: ',self)
                    pass
                else:
                    #print('HE S,L: ', self)
                    pass
                # write base(s) and read depth
                if var_type == 'S':
                    self.apply_snp(line,var_type,var_bases,read_depth)
                elif var_type == 'I':
                    self.apply_insertion(line,var_type,var_bases,read_depth)
                elif var_type == 'D':
                    for i,base in enumerate(var_bases):
                        self.apply_deletion(pse_pileup_list[pse_ind + 1 + i],var_type,base,read_depth)




    def __str__(self):
        return ' '.join([self.POS,self.REF,self.ALT,str(self.summary_flags()),self.FORMAT,self.SAMPLE,str(self.gens),str(self.ads),str(self.var_type()),
                         'HR' if self.is_homo_ref() else '-','HA' if self.is_homo_alt() else '-','U' if self.is_uncalled() else '-','HE' if self.is_het() else '-',str(self.called_bases())])





def read_vcf_quick(full_name, org,chrom,pse_pileup_list,release=None,num_recs=None):
    rec_count = 0
    head = None
    comment_lines = []
    lines = []

    tot_summary_flags = [0 for i in range(11)]
    print('  Reading: ', full_name)
    # with open(in_full_name,'r',encoding='utf-8') as vcf_file:    #OLD
    #    with gzip.open(full_name,'r') as vcf_file:                 #NEW
    vcf_file = gzip.open(full_name, 'r')
    for i, line in enumerate(vcf_file):

        if i % 500000 == 0:
            print('    Reading VCF record ', i)
        # if i > 5000:
        #    break
        line = line.decode('utf-8').rstrip()  # NEW
        # line = line.rstrip()                    #OLD
        rec_count += 1

        if line[:6] == '#CHROM':
            head = line[1:].split('\t')

            if head[-1] == org:
                pass
            else:
                print('Warning: sample in VCF ' + head[-1] + ' not equal requested strain: ' + org)

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

        v = VCFRecord(line)

        # if  var_type == 'R' or var_type == 'S' or var_type == 'F' or var_type == 'U':
        #     pass
        # else:

        pse_index = int(v.POS) -1

        if (num_recs is None):
            pass
        else:
            if pse_index  >= num_recs:
                break

        v.apply_to_pse_pileup_line(pse_index,pse_pileup_list)



        summary_flags = v.summary_flags()
        tot_summary_flags = [prev_tot + summary_flags[i] for i,prev_tot in enumerate(tot_summary_flags)]
        #lines.append(line.split('\t'))

    print(str(tot_summary_flags))
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



def process_vcf_quick(file_type, file_name, release, org, chrom, out_pse_full_name,
                                  out_vcf_full_name, num_recs=None,
                                  base_density=100000,
                                  show_plots=False):
    pse_pileup_list = create_psepileup_skeleton_from_ref(chrom, org, num_recs=num_recs)

    df, comments_lines = read_vcf_quick(file_name,org,chrom, pse_pileup_list, release=None,num_recs=num_recs)

    x = 1