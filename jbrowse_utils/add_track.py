
import argparse
import json
import copy
import logging
log = logging.getLogger(__name__)

def find_track_type(track):

    if 'label'  in track:
        spl = track['label'].split('_')
        if len(spl) > 2:
            if spl[2] == 'INDELS':
                return 'indels' # Indels
        elif len(spl) > 1:
            if spl[1] == 'VCF':
                return 'filtered' # Filtered
        else:
            return 'other' # other
    else:
        return 'other'

def find_track_species(track):
    if 'urlTemplate' in track:
        spl = track['urlTemplate'].split('seq/vcf/')
        if len(spl) > 1:
            spl2 = spl[1].split('_')
            if len(spl2) > 0:
                return spl2[0]
    return None

def find_track_strain(track):
    if 'urlTemplate' in track:
        spl = track['urlTemplate'].split('seq/vcf/')
        if len(spl) > 1:
            spl2 = spl[1].split('_strain')
            if len(spl2) > 1:
                spl3 = spl2[1].split('/')
                if len(spl3) > 0:
                    return spl3[0]
    return None


def auto_find_source_track(data, target_species, target_strain, source_type='filtered'):
    copy_from = None
    insert_point = None

    prev_track = None
    prev_track_strain = None

    track_strain_from = None

    for i, track in enumerate(data['tracks']):
        track_type = find_track_type(track)
        track_species  = find_track_species(track)
        track_strain = find_track_strain(track)
        if (track_type == source_type) and (track_species == target_species):

            if target_strain < track_strain:
               if prev_track is None:
                  copy_from = track
                  track_strain_from = track_strain

               else:
                  copy_from = prev_track
                  track_strain_from = prev_track_strain
               insert_point = i

               break
            else:
                copy_from = track
                insert_point = i + 1
                track_strain_from = track_strain

            prev_track = track
            prev_track_strain = track_strain

    return copy_from, insert_point, track_strain_from



def copy_track(data,copy_from, copy_from_strain, insert_point,strain_symbol_to, strain_name_to, source_type='filtered'):
    new_track = {}
    for el in copy_from:
        if el == 'key':
            new_track[el] = ('I/D ' + strain_name_to) if source_type == 'indels' else strain_name_to
        elif el == 'label':
            new_track[el] = (strain_symbol_to + '_VCF_INDELS') if source_type == 'indels' else (strain_symbol_to + '_VCF')
        elif el == 'urlTemplate':
            new_track[el] = copy_from[el].replace(copy_from_strain, strain_symbol_to)
        else:
            new_track[el] = copy_from[el]

    data['tracks'].insert(insert_point, new_track)
    log.info('track inserted: ' + str(new_track))

def add_track(file_name, species, strain_symbol_to, strain_name_to, verbose=0, test_run=False):
    print(file_name)
    with open(file_name, "r+") as f:
        data_in = json.load(f)

    for i, track in enumerate(data_in['tracks']):
        if verbose > 1:
            print(track)

    data_out = copy.deepcopy(data_in)

    copy_from_filtered, insert_point_filtered, strain_from_filtered = auto_find_source_track(data_out, species,
                                                                                             strain_symbol_to,
                                                                                             source_type='filtered')

    if copy_from_filtered is None:
        log.warning('Species ' + str(species) + ' not found when searching for filtered tracks to copy from. Skipping')
    else:
        copy_track(data_out, copy_from_filtered, strain_from_filtered, insert_point_filtered, strain_symbol_to, strain_name_to)

    copy_from_indels, insert_point_indels, strain_from_indels = auto_find_source_track(data_out, species,
                                                                                       strain_symbol_to,
                                                                                       source_type='indels')

    if copy_from_indels is None:
        log.warning('Species ' + str(species) + ' not found when searching for indel tracks to copy from. Skipping')
    else:
        copy_track(data_out, copy_from_indels, strain_from_indels, insert_point_indels, strain_symbol_to, strain_name_to, source_type='indels')

    if test_run:
        log.info('Test run only. No files changed')
    else:
        with open(file_name, 'w') as f:
            json.dump(data_out, f, indent=4)

    x = 1

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("file_name",help="trackList json file")
    parser.add_argument("species", help="species")
    parser.add_argument("strain_symbol_to",help="strain symbol target")
    parser.add_argument("strain_name_to",help="strain name target")
    parser.add_argument("-c", default=None, dest="strain_from", help="optional strain to copy from")
    parser.add_argument("-v",type=int,default=0,dest="verbose",help="Verbose output")
    parser.add_argument("-t", dest='test_run', action='store_true')

    args = parser.parse_args()

    add_track(args.file_name, args.species, args.strain_symbol_to, args.strain_name_to, verbose=args.verbose, test_run=args.test_run)




#
# copy_from_filtered,insert_point_filtered = find_source_track(data_in)
#
# copy_from_indels,insert_point_indels = find_source_track(data_in,source_type='indels')
#
# if copy_from_filtered is None:
#     print('template to copy from not found for filtered: ',args.strain_from)
# else:
#     copy_track(data_out,copy_from_filtered,insert_point_filtered)
#
# if copy_from_indels is None:
#     print('template to copy from not found for indels: ',args.strain_from)
# else:
#     copy_track(data_out,copy_from_indels,insert_point_indels,source_type='indels')
#
#
# for track in data_out['tracks']:
#     if args.verbose > 1:
#         print(track)
#
# with open(args.file_name, 'w') as f:
#     json.dump(data_out,f,indent=4)











