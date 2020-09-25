'''A custom Django administrative command for splitting a VCF file into a separate file for each chromosome contained within it

This command is intended to be used through Django's standard "management"
command interface, e.g.:

  # ./manage.py vcf_split <chrom strain>


'''

from django.core.management.base import BaseCommand
from django.conf import settings
from optparse import make_option
import os
import shutil
from chromosome.models import ChromosomeVCFImportFileReader
from chromosome.models import ChromosomeBatchPreprocess
from chromosome.utils import VCFRecord
from common.models import Strain, StrainSymbol
import gzip
import sys
import json
import logging
log = logging.getLogger(__name__)
from jbrowse_utils import add_track
import subprocess
from subprocess import Popen, PIPE

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
        make_option('-b', '--batch',
                    dest='batch',
                    action="store_true",
                    default=False,
                    help='Run a pending ChromosomeBatchPreprocess process'),


    )

    def assemble_input_file_name_components(self, file_name):
        path,name = os.path.split(file_name)
        chrom_part = name.split('_forPseudobase')[0]
        ext_part = '_forPseudobase' + name.split('_forPseudobase')[1]
        species_strain_part = ext_part.split('SNPS-INDELS_')[1]
        species_strain = species_strain_part.split('.')[0]
        chrom = chrom_part.split('chr')[1]
        return path,ext_part,chrom, species_strain

    def assemble_output_file(self, chrom, input_folder, ext_part, species_strain,filtered=False,indels=False):

        # file_name = 'genotyped_filtered'
        # file_name += 'ALL'
        # file_name += '_' + strain + '_chr' + chrom + '.vcf.gz'


        file_path = os.path.join(settings.JBROWSE_ROOT, settings.JBROWSE_VCF_TRACKS_PREFIX)
        file_path = os.path.join(file_path, species_strain)
        if filtered:
            file_path = os.path.join(file_path,'filtered')
        elif indels:
            file_path = os.path.join(file_path, 'indels')
        else:
            file_path = settings.PSEUDOBASE_CHROMOSOME_RAW_DATA_PENDING_PREFIX

        if not os.path.exists(file_path):
            os.umask(0)
            os.makedirs(file_path, mode=0o777)

        if filtered:
            first_part = ext_part.split('.vcf.gz')[0]
            file_path_and_name = os.path.join(file_path, 'chr' + chrom + first_part + '_filtered' + '.vcf.gz')
        elif indels:
            first_part = ext_part.split('.vcf.gz')[0]
            file_path_and_name = os.path.join(file_path, 'chr' + chrom + first_part + '_indels_only' + '.vcf.gz')
        else:
            file_path_and_name = os.path.join(file_path, 'chr' + chrom + ext_part)
        return file_path_and_name

    def perl_postprocess(self, file_name):
        '''
           Post-process filtered and indel files using perl utilities (reequired for JBrowse VCF tracks):
           unzip -> bgzip -> tabix
        '''

        try:
            log.info('Unzipping: ' + file_name)
            ret = subprocess.call([settings.JBROWSE_PERL_GUNZIP_PATH, '-f', file_name])
            log.info('Unzip result: ' + file_name + ' : ' + str(ret))
            log.info('bgzipping: ' + file_name.split('.gz')[0])
            ret = subprocess.call([settings.JBROWSE_PERL_BGZIP_PATH, '-f', file_name.split('.gz')[0]])
            log.info('bgzip result: ' + file_name.split('.gz')[0] + ' : ' + str(ret))
            log.info('tabixing: ' + file_name)
            ret = subprocess.call([settings.JBROWSE_PERL_TABIX_PATH, file_name, '-p', 'vcf'])
            log.info('tabix result: ' + file_name + ' : ' + str(ret))

        except Exception as e:
            log.warning('Perl postprocessing failed for: ' + file_name + ' Error: ' + str(e))


    def split(self,file_name,ext_part,path,species_strain,reduce=False,indels=False, process_in_batch=False, batch=None):
        vcf_reader = ChromosomeVCFImportFileReader(file_name)
        file_name_in = file_name
        file_part = os.path.split(file_name_in)[1]
        tot_records = vcf_reader.get_num_records()
        _ , strain_symbol_in_file = vcf_reader.get_chrom_and_strain()
        if process_in_batch:
            prog_list = json.loads(batch.final_report)
            prog_rec = None
            for rec in prog_list:
                if rec['file'] == file_part:
                    prog_rec = rec
            if prog_rec is None:
                pass
            else:
                prog_rec['total_records'] = tot_records
                prog_rec['status'] = 'A'
                prog_rec['strain'] = species_strain
                prog_rec['chroms'] = ''

                batch.final_report = json.dumps(prog_list)
                batch.save()


        vcf_reader.open()
        comments = []
        lines = []
        chroms = {}

        not_passed = 0
        not_called = 0
        hom_ref = 0
        stars = 0

        for i, line in enumerate(vcf_reader.vcf_file):
            if i % 10000 == 0:
                #sys.stdout.write('.')
                #sys.stdout.flush()
                if i % 250000 == 0:
                    self.stdout.write(' Processing: ' + str(i) + ' / ' + str(tot_records))
                if process_in_batch:
                    prog_list = json.loads(batch.final_report)
                    prog_rec = None
                    for rec in prog_list:
                        if rec['file'] == file_part:
                            prog_rec = rec
                    if prog_rec is None:
                       pass
                    else:
                        prog_rec['records_read'] = i
                        if prog_rec['total_records'] == 0:
                            pass
                        else:
                           prog_rec['perc_complete'] = prog_rec['records_read'] * 1.0  / prog_rec['total_records'] * 100.0
                        chroms_list = prog_rec['chroms'].split(', ')
                        if len(chroms_list) == 1 and (chroms_list[0] == ''):
                            pass
                        else:
                            updated_chroms_list = []
                            for chrom_rec in chroms_list:
                                num_filtered = 0
                                num_indels = 0
                                chrom = chrom_rec.split(' [')[0]
                                if chrom in chroms:
                                   if 'filtered_records' in chroms[chrom]:
                                      num_filtered = chroms[chrom]['filtered_records']
                                   if 'indel_records' in chroms[chrom]:
                                       num_indels = chroms[chrom]['indel_records']
                                updated_chroms_list.append(chrom + ' [Filtered: ' + str(num_filtered) + ' Indels: ' + str(num_indels) + ']')
                            prog_rec['chroms'] = ', '.join(updated_chroms_list)

                    batch.final_report = json.dumps(prog_list)
                    batch.save()


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
                       log.info('Creating out file name: ' + file_name)
                       f = gzip.open(file_name, 'wb')
                       chroms[v.CHROM] = {'file': f,  'file_name': file_name, 'records': 1}
                       out_comments_str = '\n'.join(comments)
                       f.write(out_comments_str)
                       f.write('\n')
                       f.write(line.encode())

                       if process_in_batch:
                           prog_list = json.loads(batch.final_report)
                           prog_rec = None
                           for rec in prog_list:
                               if rec['file'] == file_part:
                                   prog_rec = rec
                           if prog_rec is None:
                               pass
                           else:
                               if prog_rec['chroms'] == '':
                                   chroms_list = []
                               else:    
                                   chroms_list = prog_rec['chroms'].split(', ')
                               chroms_list.append(v.CHROM + ' [Filtered: 0 Indels: 0]')
                               prog_rec['chroms'] = ', '.join(chroms_list)
                               batch.final_report = json.dumps(prog_list)
                               batch.save()

                       if reduce:
                           file_name_filtered = self.assemble_output_file(v.CHROM, path, ext_part, species_strain,filtered=True)
                           log.info('Creating filtered out file name: ' + file_name_filtered)
                           f_filtered = gzip.open(file_name_filtered, 'wb')
                           chroms[v.CHROM]['filtered_file'] =  f_filtered
                           chroms[v.CHROM]['filtered_file_name'] = file_name_filtered
                           f_filtered.write(out_comments_str)
                           if skip_this_record:
                               chroms[v.CHROM]['filtered_records'] = 0
                           else:
                               chroms[v.CHROM]['filtered_records'] = 1
                               f_filtered.write('\n')
                               f_filtered.write(line_simplified.encode())
                       if indels:
                           file_name_indels = self.assemble_output_file(v.CHROM, path, ext_part, species_strain, indels=True)
                           log.info('Creating indels out file name: ' + file_name_indels)
                           f_indels = gzip.open(file_name_indels, 'wb')
                           chroms[v.CHROM]['indel_file'] = f_indels
                           chroms[v.CHROM]['indel_file_name'] = file_name_indels
                           f_indels.write(out_comments_str)
                           if skip_this_record or not (var_type == 'I' or var_type == 'D') :
                               chroms[v.CHROM]['indel_records'] = 0
                           else:
                               chroms[v.CHROM]['indel_records'] = 1
                               f_indels.write('\n')
                               f_indels.write(line_simplified.encode())


        log.info(' ')
        log.info(' Num comment lines: ' + str(len(comments)))
        if reduce:
            log.info(' Ignoring for filtered file:')
            log.info('   Not passed: ' + str(not_passed))
            log.info('   Hom Ref: ' + str(hom_ref))
            log.info('   Uncalled: ' + str(not_called))
            log.info('   *: ' + str(stars))
        for chrom in chroms:
            log.info(' chrom: ' + chrom + ' records: ' + str(chroms[chrom]['records'])  +  ' - closing ')
            f = chroms[chrom]['file']
            f.close()
            if reduce:
                log.info(' chrom: ' + chrom + ' filtered records: ' + str(chroms[chrom]['filtered_records']) + ' - closing ')
                f = chroms[chrom]['filtered_file']
                f.close()
                if settings.JBROWSE_PERL_POSTPROCESS:
                    self.perl_postprocess(chroms[chrom]['filtered_file_name'])
            if indels:
                log.info(' chrom: ' + chrom + ' indel records: ' + str(chroms[chrom]['indel_records']) + ' - closing ')
                f = chroms[chrom]['indel_file']
                f.close()
                if settings.JBROWSE_PERL_POSTPROCESS:
                    self.perl_postprocess(chroms[chrom]['indel_file_name'])


        log.info(' Finished reading vcf. Num records: ' + str(i))

        vcf_reader.close()

        if process_in_batch:
            prog_list = json.loads(batch.final_report)
            prog_rec = None
            for rec in prog_list:
                if rec['file'] == file_part:
                    prog_rec = rec
            if prog_rec is None:
                pass
            else:
                prog_rec['records_read'] = i + 1
                prog_rec['status'] = 'Complete'
                batch.final_report = json.dumps(prog_list)
                batch.save()

        return chroms,comments, strain_symbol_in_file

    def output_file(self,file_name,comments,contents):

        out_comments_str = '\n'.join(comments)

        out_vcf_str = '\n'.join(contents)

        out_str = '\n'.join([out_comments_str, out_vcf_str])

        log.info('Writing: ' + file_name)


        f = gzip.open(file_name, 'wb')
        f.write(out_str.encode())
        f.close()

    def _process_batch_preprocess_request(self, batch, options):


        log.info('Number of files to process: ' + str(batch.num_files_in_batch()))
        log.info('Preprocessing: ' + str(batch))

        try:
            # Set up our work area.
            # working_directory, results_directory = self._setup_work_area()

            # Indicate that the request is currently being processed.
            batch.start()  # In Progress

            batch_file_list = [batch_file.strip() for batch_file in batch.original_request.split('\n')]
            prog_list = []
            for batch_file in batch_file_list:
                prog_list.append(
                        {'file': os.path.split(batch_file)[1], 'records_read': 0, 'total_records': 0, 'perc_complete': 0,
                         'status': 'Pending', 'chroms': '', 'strain': ''})
            batch.final_report = json.dumps(prog_list)

            batch.save()  # save immediately,so no other process will start

            species_strains = {}


            # For each file in batch:
            #     - Call split routine (split performs splits/filtering then moves split files to pending imports directory, filtered/indels files to jbrowse vcf tracks directory)
            #     - move file to processed directory
            for batch_file in batch_file_list:
                try:
                    path, ext_part, in_chrom, species_strain = self.assemble_input_file_name_components(batch_file)
                    log.info('*******************')
                    log.info(' Input file: ' + batch_file)
                    log.info('Chrom group: ' + in_chrom)
                    log.info(' Species/Strain: ' + species_strain)

                    chroms, comments, strain_symbol_in_file = self.split(batch_file, ext_part, path, species_strain,
                                                  reduce=options['filter'], indels=options['indels'], process_in_batch=True, batch=batch)

                    if species_strain in species_strains:
                        if strain_symbol_in_file in species_strains[species_strain]['symbols']:
                            pass
                        else:
                            species_strains[species_strain]['symbols'].append(strain_symbol_in_file)

                    else:
                        species_strains[species_strain] = {'symbols': [species_strain.split('_strain')[1]]}
                        if strain_symbol_in_file in species_strains[species_strain]['symbols']:
                            pass
                        else:
                            species_strains[species_strain]['symbols'].append(strain_symbol_in_file)



                    shutil.move(batch_file, os.path.join(settings.PSEUDOBASE_CHROMOSOME_RAW_DATA_VCF_PREFIX,'processed/'))

                except Exception as e:
                    log.warning('chromosome preprocess failed: ' +  batch_file +  ' Reason: ' + str(e))
                    pass

                # For each unique species/strain encountered in batch files:
                # Add Strain, StrainSymbol and StrainCollectionInfo in database
            for species_strain in species_strains:
                try:
                    Strain.objects.add_strain(strain_name=species_strain.split('_strain')[1],
                                              species_symbol=species_strain.split('_strain')[0][1:],
                                              strain_symbols=species_strains[species_strain]['symbols'])
                except Exception as e:
                    log.warning('Strain add failed: ' + str(e))

            # For each unique species/strain encountered in batch files:
            #   - Add JBrowse filtered and indels tracks to JBrowse config trackList.json file in order to show in JBrowse
            for species_strain in species_strains:
                tracklist_file_name = os.path.join(settings.JBROWSE_ROOT, settings.JBROWSE_CONFIG_FILE)
                try:
                    strain_record  = StrainSymbol.objects.get(symbol=species_strain.split('_strain')[1])
                    strain_name = strain_record.strain.name
                except:
                    strain_name = species_strain.split('_strain')[1] # Just use strain symbol as name

                add_track.add_track(tracklist_file_name, species_strain.split('_strain')[0], species_strain.split('_strain')[1], strain_name)


            batch.stop(batch_status='C')
            batch.save()

        except Exception:
            batch.stop(batch_status='F')
            batch.save()
            raise


    def process_batch(self, options):

        '''

         1) Check if any Chromosome Batch Preprocess processes are already running
                => If so: exit (one at a time!)

         2) Check for any Pending Chromosome Batch Preprocess processes
                => If found: execute one

        '''

        running_batches = ChromosomeBatchPreprocess.objects.running_batches()
        if (len(running_batches) > 0):
            log.info('Batch already running. Exiting')
            return

        pending_batches = ChromosomeBatchPreprocess.objects.pending_batches()

        if (len(pending_batches) > 0):
            self._process_batch_preprocess_request(pending_batches[0], options)
        else:
            log.info('No pending batches to process')

    def handle(self,  **options):
            '''The main entry point for the Django management command.

            '''

            if options['batch']:
                log.info('Running batch preprocess')
            else:
                log.info('Number of files to process: ' + str(len(options['file_list'])))
            log.info('Also create reduced VCF with called variants only (SNPS and INDELS) for strain: ' + str(options['filter']))
            log.info('Also create reduced VCF with called INDEL variants only for strain: ' + str(options['indels']))

            if options['batch']:
               self.process_batch(options)
            else:
               for file_name in options['file_list']:
                    path,ext_part,in_chrom,species_strain = self.assemble_input_file_name_components(file_name)
                    log.info('*******************')
                    log.info(' Input file: ' + file_name)
                    log.info(' Chrom group: ' + in_chrom)
                    log.info(' Species/Strain: ' + species_strain)


                    chroms,comments, strain_symbol_in_file = self.split(file_name,ext_part,path,species_strain,reduce=options['filter'],indels=options['indels'])

            # for chrom in chroms:
            #       out_name = self.assemble_output_file(chrom,path,ext_part,species_strain)
            #       self.output_file(out_name,comments,chroms[chrom])






