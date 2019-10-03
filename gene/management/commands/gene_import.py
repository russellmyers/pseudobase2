'''A custom Django administrative command for importing gene data.

This command imports gene data from a CSV-like file provided by the Noor lab.
Each "record" (i.e. an individual sequence of gene data) is created as an
individual object within the database.

The supported format for this command is as follows (tab-delimited):
Field 1: chromsome name, appended with underscore and first base position
  e.g. 2_1772
Field 2: import code
  e.g. dpse_GLEANR_4729
Field 3: strand (this field can be ignored)
Field 4: species code (translate into appropriate full species name)
  e.g. pse
Field 5: strain code (translate into appropriate full strain name)
  e.g. pp134
Field 6: bases (sequence data)
  e.g. ATGCGCCGG...

'''

import csv
import os
import re
import sys
import gzip
import pandas as pd

import django.utils.timezone
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection, transaction

from common.models import Chromosome, StrainSymbol
from gene.models import Gene, GeneImportLog, MRNA, CDS

from optparse import make_option

class GFFReader():
    def __init__(self,command,fPath,excl_match=True,excl_gold_path = True,chrom_names=None,ignore_fasta=True, limit=None):
        self.fPath = fPath
        self.command = command
        self.excl_match = excl_match
        self.excl_gold_path = excl_gold_path
        self.chrom_names = chrom_names

        gff_list = []

        all_chrom_info = {}

        comments = []

        fasta_stuff = []

        fin = gzip.open(self.fPath, 'r')
        for i, line in enumerate(fin):

            if i % 1000000 == 0:
                 sys.stdout.write('.')
                 sys.stdout.flush()

            if limit is None:
                pass
            else:
                if i > limit:
                    break

            line_str = line.decode('utf-8').rstrip()
            line_parsed = line_str.split('\t')

            if line_parsed[0][:2] == '##':
                comments.append([i, line_parsed])
                continue
            elif len(line_parsed) < 2:
                if ignore_fasta:
                    pass
                else:
                    fasta_stuff.append([i, line_parsed])
                continue

            if self.excl_match:
                if line_parsed[2] == 'match':
                    continue

                if line_parsed[2] == 'match_part':
                    continue

            if self.excl_gold_path:
                if line_parsed[2] == 'golden_path_region':
                    continue  # causes chunk size problems in jbrowse

            if self.chrom_names is None: # incl all
                gff_list.append(line_parsed)
            elif line_parsed[0] in self.chrom_names:  # == chrom_name:
                # print('i: ' + str(i) + ' line: ' + line_str[:150])
                gff_list.append(line_parsed)

            if line_parsed[2] == 'gene':
                if line_parsed[0] in all_chrom_info:
                    all_chrom_info[line_parsed[0]]['num_genes'] += 1
                    if line_parsed[6] == '+':
                        all_chrom_info[line_parsed[0]]['num_pos'] += 1
                    else:
                        all_chrom_info[line_parsed[0]]['num_neg'] += 1
                else:
                    all_chrom_info[line_parsed[0]] = {'num_genes': 1}
                    if line_parsed[6] == '+':
                        all_chrom_info[line_parsed[0]]['num_pos'] = 1
                        all_chrom_info[line_parsed[0]]['num_neg'] = 0
                    else:
                        all_chrom_info[line_parsed[0]]['num_neg'] = 1
                        all_chrom_info[line_parsed[0]]['num_pos'] = 0

        fin.close()
        df = pd.DataFrame(gff_list,
                          columns=['seqid', 'source', 'type', 'start', 'end', 'score', 'strand', 'phase', 'attributes'])
        self.df = df
        self.all_chrom_info = all_chrom_info
        self.comments = comments
        self.fasta_stuff = fasta_stuff


    def gleanr(self,name_list):
        for name in name_list:
            if name[:11] == 'dpse_GLEANR':
                return name
        return ''


    def attr_to_name_list(self,attr):
        attr_list = attr.split(';')
        #attr_dict = {x.split('=')[0]: x.split('=')[1] for x in attr_list}
        attr_dict = dict((x.split('=')[0], x.split('=')[1]) for x in attr_list)
        names = []
        if 'ID' in attr_dict:
            names.append(attr_dict['ID'])
        if 'Name' in attr_dict:
            names.append(attr_dict['Name'])
        if 'Alias' in attr_dict:
            aliases = attr_dict['Alias'].split(',')
            names.extend(aliases)
        return names


    def attr_split(self,attr):
        attr_list = attr.split(';')
        #attr_dict = {x.split('=')[0]: x.split('=')[1] for x in attr_list}
        attr_dict = dict((x.split('=')[0], x.split('=')[1]) for x in attr_list)
        all_names = self.attr_to_name_list(attr)
        import_code = ''
        # for name in all_names:
        #     if name[:11] == 'dpse_GLEANR':
        #         import_code = name
        #         break
        if 'ID' in attr_dict:
            import_code = attr_dict['ID']

        return pd.Series(
            [attr_dict['ID'] if 'ID' in attr_dict else '', attr_dict['Parent'] if 'Parent' in attr_dict else '',
             attr_dict['Name'] if 'Name' in attr_dict else '', import_code,
             attr_dict['Alias'] if 'Alias' in attr_dict else ''])

    def split_attributes(self,df):
        df_spl = df.copy()
        df_spl[['ID', 'Parent', 'Name', 'Import_Code', 'Alias']] = df_spl['attributes'].apply(self.attr_split)
        df_spl.head()
        return df_spl


    def pre_parse(self,df):
        parent_dict = {}
        gene_dict = {}
        mrna_dict = {}

        i = 0
        for index, row in df.iterrows():

            if i % 10000 == 0:
                print('Processing: ', i, ' / ', df.shape[0])
            i += 1

            if row['type'] == 'gene':
                if row['ID'] in gene_dict:
                    print('Dup found: ', row['ID'])
                else:
                    gene_dict[row['ID']] = row
            if row['type'] == 'mRNA':
                if row['ID'] in mrna_dict:
                    print('Dup found: ', row['ID'])
                else:
                    mrna_dict[row['ID']] = row

            if (row['ID'] == '') or (row['Parent'] == ''):
                pass
            else:
                if row['ID'] in parent_dict:
                    print('Dup parent rec found: ', row['ID'])
                else:
                    parent_dict[row['ID']] = row['Parent']

        self.parent_dict = parent_dict
        self.gene_dict = gene_dict
        self.mrna_dict = mrna_dict

    def find_gene(self,parent):
        # print('finding: ',parent)
        done = False
        curr_parent = parent
        while not done:
            if curr_parent in self.gene_dict:
                return curr_parent

            if curr_parent in self.parent_dict:
                curr_parent = self.parent_dict[curr_parent]
            else:
                done = True
                return None

    def find_mrna(self,parent):
        # print('finding: ',parent)
        done = False
        curr_parent = parent
        while not done:
            if curr_parent in self.mrna_dict:
                return curr_parent

            if curr_parent in self.parent_dict:
                curr_parent = self.parent_dict[curr_parent]
            else:
                done = True
                return None

    def allocate_gene_and_mrna_per_record(self,df):

        gene_list = []
        mrna_list = []

        df_new = df.copy()

        i = 0
        for index, row in df.iterrows():

            if i % 10000 == 0:
                print('Processing: ', i, ' / ', df.shape[0])
            i += 1

            if row['type'] == 'gene':
                gene_list.append(row['ID'])
                mrna_list.append(None)
            else:
                if row['type'] == 'mRNA':
                    mrna_list.append(row['ID'])
                else:
                    if row['Parent'] == '':
                        mrna_list.append(None)
                    else:
                        mrna = self.find_mrna(row['Parent'])
                        if mrna is None:
                            mrna_list.append(None)
                        else:
                            mrna_list.append(mrna)

                if row['Parent'] == '':
                    gene_list.append(None)
                else:
                    gene = self.find_gene(row['Parent'])
                    if gene is None:
                        gene_list.append(None)
                    else:
                        gene_list.append(gene)

        df_new['gene'] = gene_list
        df_new['mrna'] = mrna_list
        return df_new

    def mrna_rows_for_gene(self,gene_row, mrna_dict):
        # mrna_dict[row['ID']]= {'Name':row['Name'],'CDS':[]}

        out_rows = []
        if len(mrna_dict) == 0:
            out_row = gene_row.copy()
            out_row['mrna_name'] = ''
            out_row['CDS'] = []
            out_rows.append(out_row)
        else:
            for mrna_id in mrna_dict:
                out_row = gene_row.copy()
                entry = mrna_dict[mrna_id]
                out_row['mrna_name'] = entry['Name']
                out_row['CDS'] = entry['CDS']
                out_rows.append(out_row)

        return out_rows


    def find_mrnas_and_cds_per_gene(self,df):
        gene_list = []
        gene_cds_regions = []

        mrna_dict = {}

        cds_dict = {}

        in_gene = False

        out_row = None

        gene_import_code = ''
        gene_row = None
        first_gene = True

        num_genes = 0
        num_genes_with_mrna = 0
        num_genes_with_multi_mrna = 0
        num_genes_with_CDS = 0

        gene_parents = []
        gene_id = None


        i = 0
        for index, row in df.iterrows():

            if i % 10000 == 0:
                #print('\r', 'Processing: ', i, ' / ', df.shape[0], end='')
                print('Processing: ', i, ' / ', df.shape[0])
            i += 1

            if row['type'] == 'gene':
                in_gene = True
                # print('last gene parents: ',gene_parents)
                if first_gene:
                    first_gene = False
                else:
                    #             gene_row['mrna_dict'] = mrna_dict
                    #             gene_list.append(gene_row)
                    gene_list.extend(self.mrna_rows_for_gene(gene_row, mrna_dict))

                    num_genes += 1
                    if len(mrna_dict) == 0:
                        pass
                    else:
                        num_genes_with_mrna += 1
                        if len(mrna_dict) > 1:
                            num_genes_with_multi_mrna += 1
                        for mrna_id in mrna_dict:
                            if len(mrna_dict[mrna_id]['CDS']) > 0:
                                num_genes_with_CDS += 1
                                break

                # gene_cds_regions.append([gene_id,gene_import_code,mrna_dict])
                mrna_dict = {}
                gene_parents = [row['ID']]
                #         gene_id = row['ID']
                #         gene_name = row['Name']
                #         gene_import_code = row['Import_Code']
                #         row['parent_gene_id'] = gene_id
                #         row['parent_gene_name'] = row['Name']
                #         row['mrna_dict'] = mrna_dict
                gene_row = row.copy()
                # gene_list.append(row)
            else:
                if row['Parent'] in gene_parents:
                    # row['parent_gene_id'] = gene_id
                    # row['parent_gene_name'] = gene_name
                    if row['ID'] == '':
                        pass
                    else:
                        gene_parents.append(row['ID'])
                    # gene_list.append(row)
                    if row['type'] == 'mRNA':
                        if row['ID'] in mrna_dict:
                            print('Oh oh - already in: ', row['ID'])
                        else:
                            mrna_dict[row['ID']] = {'Name': row['Name'], 'CDS': []}

                    if row['type'] == 'CDS':
                        if row['Parent'] in mrna_dict:
                            mrna_dict[row['Parent']]['CDS'].append([row['start'], row['end']])

                        else:
                            print('Parent mrna not found for: ', row['ID'])

                        if gene_id in cds_dict:
                            cds_dict[gene_id].append([[row['start'], row['end']]])
                        else:
                            cds_dict[gene_id] = [[row['start'], row['end']]]

                else:
                    pass
        #           in_gene = False
        #           gene_parents = []
        #           gene_id = None


        # gene_cds_regions.append([gene_id,gene_import_code,mrna_dict])
        gene_list.extend(self.mrna_rows_for_gene(gene_row, mrna_dict))
        num_genes += 1
        if len(mrna_dict) == 0:
            pass
        else:
            num_genes_with_mrna += 1
            if len(mrna_dict) > 1:
                num_genes_with_multi_mrna += 1
            for mrna_id in mrna_dict:
                if len(mrna_dict[mrna_id]['CDS']) > 0:
                    num_genes_with_CDS += 1
                    break

        df_gene_ids = pd.DataFrame(gene_list)

        print('Num genes: ',num_genes)
        print('Num genes with mrna: ',num_genes_with_mrna)
        print('Num genes with CDS: ',num_genes_with_CDS)
        print('Num genes with multi mRNA: ',num_genes_with_multi_mrna)

        return df_gene_ids


    def write_genes(self,df,import_log):

        ref_strain_symbol = 'MV2-25'

        df_gene_grouped = df[df['type'] == 'CDS'].groupby(['gene'])
        for gene_id, gene_records in df_gene_grouped:
            import_log.gene_count += 1
            # A simple progress indicator, since processing can take a while.
            # Show progress after every thousand genes processed.
            if (import_log.gene_count % (1000)) == 1:
                sys.stdout.write('.')
                sys.stdout.flush()

            gene_row = self.gene_dict[gene_id]
            chromosome_name = gene_row['seqid']
            start_position = int(gene_row['start'])
            end_position = int(gene_row['end'])
            import_code = gene_row['Import_Code']
            strand = gene_row['strand']
            bases = ''  # Bases are now derived from ChromosomeBase, unless overriddenn here

            try:
                current_g = self._save_gene(chromosome_name, ref_strain_symbol, start_position,
                                                import_code,strand, bases, end_position=end_position)
                df_mrna_grouped = gene_records.groupby(['mrna'])
                for mrna_id, mrna_cds_records in df_mrna_grouped:
                    mrna_row = self.mrna_dict[mrna_id]
                    mRNA = self._save_mrna(current_g, mrna_row,mrna_cds_records) # mRNA_name, row['CDS'])
                    #mRNA_name = row['mrna_name']
                    # for i, row in mrna_cds_records.iterrows():
                    #     print('       CDS: ', row['start'], row['end'])
            except:
                self.command._rollback_db()
                raise

        # current_g = None
        # for index,row in df.iterrows():
        #
        #     if len(row['CDS']) == 0:
        #         continue
        #
        #     import_log.gene_count += 1
        #     # A simple progress indicator, since processing can take a while.
        #     # Show progress after every thousand genes processed.
        #     if (import_log.gene_count % (1000)) == 1:
        #         sys.stdout.write('.')
        #         sys.stdout.flush()
        #
        #     chromosome_name = row['seqid']
        #     start_position =  int(row['CDS'][0][0])
        #     end_position = int(row['CDS'][-1][-1])
        #     import_code = row['Import_Code']
        #     mRNA_name = row['mrna_name']
        #     strand = row['strand']
        #
        #     # Process strain.
        #
        #     bases = ''  #Bases are now derived from ChromosomeBase, unless overriddenn here
        #
        #     try:
        #         if current_g is not None and current_g.import_code == import_code:
        #             pass
        #         else:
        #             current_g = self._save_gene(chromosome_name, ref_strain_symbol, start_position,
        #                         import_code, bases,end_position=end_position)
        #         mRNA = self._save_mrna(current_g, mRNA_name, row['CDS'])
        #     except:
        #         self.command._rollback_db()
        #         raise

    def _save_gene(self, chromosome_name, strain_name, start_position,
                   import_code, strand, bases, end_position=None):
        '''Create and save a new gene constructed from the passed data.

        Type coercion can happen here, but any other data munging should
        occur before this method is called.

        '''


        g = Gene()
        g.strain = self.command._lookup_strain(strain_name)[0]
        g.chromosome = self.command._lookup_chromosome(chromosome_name)[0]
        g.start_position = int(start_position)
        if end_position is None:
            g.end_position = int(start_position + (len(bases) - 1))
        else:
            g.end_position = int(end_position)
        g.import_code = import_code
        g.strand = strand
        g.bases = bases
        g.save()
        return g

    def _save_cds(self,m,st,end,num):
        cds = CDS()
        cds.mRNA = m
        cds.start_position = st
        cds.end_position = end
        cds.num = num
        cds.save()


    def _save_mrna(self, g, mrna_row,mrna_cds_records): # name, cds_ranges):
        try:
            mRNA = MRNA()
            mRNA.name = mrna_row['Name']
            mRNA.gene = g
            mRNA.save()
            num = 0
            for index, cds_row in mrna_cds_records.iterrows():
               # print('       CDS: ', row['start'], row['end'])
               # for i,cds_range in enumerate(cds_ranges):
                num += 1
                self._save_cds(mRNA,int(cds_row['start']),int(cds_row['end']),num)



        except:
            self.command._rollback_db()
            raise

class Command(BaseCommand):
    '''A custom command to import gene data from a CSV-like file.'''
    
    help = 'Imports the data from the named file into the database.'
    args = '<path to CSV-like file>'

    option_list = BaseCommand.option_list + (
        make_option('-l', '--limit',
                    dest='limit',
                    type = int,
                    default=None,
                    help='Max number of records to read from gff (testing purposes only)'),
        make_option('-c', '--chrom',
                    dest='chrom_list',
                    default = [],
                    action = 'append',
                    help='import chromosome name'),

    )

    def _lookup_strain(self, strain):
        '''Load a Strain object for association by its "short name".
    
        First, translate the "short name" of the strain into the appropriate
        "full name".  Then, look up the "full name" to get the related object
        which we can then use for associations.
        '''
        
#       OLD NOTE: We could (should) do this programmatically if we added a table
#       that mapped common strain notation to the appropriate Strain object.
#       It isn't necessary during the time crunch (a.k.a. now), but it should
#       probably be done if the translation table ends up changing often.
        
        
#       NEW NOTE: DONE! Below hard coded strain_translation is now replaced with StrainSymbol table:        


#        STRAIN_TRANSLATION = {
#          'AFC12':    'American Fork Canyon, UT 12',
#          'FLAG14':   'Flagstaff, AZ 14',
#          'FLAG16':   'Flagstaff, AZ 16',
#          'FLAG18':   'Flagstaff, AZ 18',
#          'MATHER32': 'Mather, CA 32',
#          'MATHERTL': 'Mather, CA TL',
#          'MV2_25':   'Mesa Verde, CO 2-25 reference line',
#          'MSH9':     'Mount St. Helena, CA 9',
#          'MSH24':    'Mount St. Helena, CA 24',
#          'PP1134':   'San Antonio, NM, Pikes Peak 1134',
#          'PP1137':   'San Antonio, NM, Pikes Peak 1137',
#          'ERW':      'El Recreo white mutant line',
#          'TORO':     'Torobarroso',
#          'MSH1993':  'Mount St. Helena, CA 1993',
#          'MSH39':    'Mount St. Helena, CA 39',
#          'SCISR':    'Santa Cruz Island',
#          'MSH22':    'Mount St. Helena, CA 22',
#          'MSH3':     'Mount St. Helena, CA 3',
#          'SP138':    'SP138',
#          'MAO':      'MAO',
#          'ARIZ':     'Lowei',
#        }
    
#        if strain.upper() in STRAIN_TRANSLATION:
#            lookup_strain = STRAIN_TRANSLATION[strain.upper()]
        try:
            s = StrainSymbol.objects.get(symbol=strain.upper()).strain
            return (s, False)
        except:
            print ('not found: ',strain.upper())
            raise
  
    def _lookup_chromosome(self, chromosome):
        '''Load a Chromosome object for association by its name.'''
        return (Chromosome.objects.get(name=chromosome), False)
  
    def _save_gene(self, chromosome_name, strain_name, start_position,
      import_code, strand, bases,end_position=None):
        '''Create and save a new gene constructed from the passed data.
        
        Type coercion can happen here, but any other data munging should 
        occur before this method is called.
    
        '''
      
        g = Gene()
        g.strain = self._lookup_strain(strain_name)[0]
        g.chromosome = self._lookup_chromosome(chromosome_name)[0]
        g.start_position = int(start_position)
        if end_position is None:
            g.end_position = int(start_position + (len(bases) - 1))
        else:
            g.end_position = int(end_position)
        g.import_code = import_code
        g.strand = strand
        g.bases = bases
        g.save()
        return g

    def _rollback_db(self):
        '''Roll back the database transaction (use in error conditions.)'''
        
        transaction.rollback()
        transaction.leave_transaction_management()

    def handle(self, gene_data, **options):
        '''The main entry point for the Django management command.
    
        Iterates through the lines in the specified file.  Each line contains
        sequence data for a particular gene.  Once massaged into appropriate
        formats, a new Gene object is created and saved to the database.
    
        WARNING: This script can take up a lot of resources when processing a
        file with a lot of gene sequences.  Steps have been taken to minimize 
        the impact, but there is only so much that can be done.  Plan to have 
        a large (10K+ records) file take a few minutes to process.
    
        '''
    
        time_begin = django.utils.timezone.now()
    
        print 'Constructing Gene objects from file:\n%s' % gene_data
        print '  ',

        gff_based_import = True

        name_split = gene_data.split('.')
        if len(name_split) > 2:
            if ((name_split[-2] == 'gff') or (name_split[-2] == 'gff3')) and name_split[-1] == 'gz':
                gff_reader = GFFReader(self,gene_data,chrom_names = options['chrom_list'],limit=options['limit'])
                gff_reader.df = gff_reader.split_attributes(gff_reader.df)
                gff_reader.pre_parse(gff_reader.df)
                gff_reader.df = gff_reader.allocate_gene_and_mrna_per_record(gff_reader.df)
                #gff_reader.df_gene_ids = gff_reader.find_mrnas_and_cds_per_gene(gff_reader.df)
            else:
                gff_based_import = False
        else:
            gff_based_import = False


        if gff_based_import:
            pass
        else:
            gene_reader = csv.reader(open(gene_data, 'r'), delimiter='\t')
    
        # Start transaction management.
        transaction.commit_unless_managed()
        transaction.enter_transaction_management()
        transaction.managed(True)
        
        # Create a new ImportLog object to store metadata about the import.
        import_log = GeneImportLog(start=time_begin, 
          file_path=os.path.abspath(gene_data), gene_count=0)
    
        split_search = re.compile(r'^(.+)_(\d+)$').search
        char_search = re.compile(r'[^ACTGN\_]').search
        replace_no_data = re.compile(r'[_]').sub

        if gff_based_import:
            gff_reader.write_genes(gff_reader.df,import_log)
        else:
            for line in gene_reader:
                # Skip empty lines.
                if not line: continue

                # Skip the header line.
                if line[0] == 'base': continue

                import_log.gene_count += 1
                # A simple progress indicator, since processing can take a while.
                # Show progress after every thousand genes processed.
                if (import_log.gene_count % (1000)) == 1:
                    sys.stdout.write('.')
                    sys.stdout.flush()

                # Process chromosome and start_position.
                m = split_search(line[0])
                chromosome_name = m.group(1)
                start_position = int(m.group(2))

                # Process import_code.
                import_code = line[1]

                # Process strain.
                strain_name = line[4].upper().replace(r'BDA', '')

                strand = '-' if line[2] == 'm' else '+'

                # Process bases.
                # Check that the base string contains no invalid characters.
                bases = line[5]

                # Check that the base string contains no invalid characters.
                if char_search(bases):
                    print "Invalid character detected in base for line: '%s'" % \
                      bases
                    break
                else:
                    # Change "D" characters in the base column to "-".
                    bases = replace_no_data(r'-', bases)

                try:
                    self._save_gene(chromosome_name, strain_name, start_position,
                      import_code, strand, bases)
                except:
                    self._rollback_db()
                    raise

        # Finish populating the import meta-data.
        import_log.end = django.utils.timezone.now()
        import_log.calculate_run_time()

        # Only save the import metadata if we actually did anything.
        if import_log.gene_count > 0:    
            try:
                import_log.save()
            except:
                self._rollback_db()
                raise
    
        # Finalize the transaction and close the db connection.
        transaction.commit()
        transaction.leave_transaction_management()
        connection.close()
    
        # All lines of gene data have been processed, so we can print a short
        # summary of what we did.
        td = import_log.end - import_log.start
        print '\nProcessing complete in %s days, %s.%s seconds.' % (td.days,
          td.seconds, td.microseconds)
        print '  Gene objects constructed: %s' % import_log.gene_count
