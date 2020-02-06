
import argparse
import json
import copy


parser = argparse.ArgumentParser()
parser.add_argument("file_name",help="trackList json file")
parser.add_argument("strain_from",help="strain to copy from")
parser.add_argument("strain_symbol_to",help="strain symbol to")
parser.add_argument("strain_name_to",help="strain name to")


args = parser.parse_args()
print(args.file_name)

with open(args.file_name,"r+") as f:
    data_in = json.load(f)

for i,track in enumerate(data_in['tracks']):
    print(track)

data_out = copy.deepcopy(data_in)



def find_source_track(data,source_type='filtered'):
    copy_from = None
    insert_point = None

    for i,track in enumerate(data['tracks']):
        templ = track['urlTemplate']
        spl = templ.split('/' + source_type)
        if len(spl) > 1:
            spl2 = spl[0].split('strain')
            if len(spl2) > 1:
                sym = spl2[1]
                print('sym is: ',sym, 'for: ',templ)
            else:
                print('cant find symbol for: ',templ)
                continue
            if sym == args.strain_from:
                print('aha!!: ',sym)
                insert_point = i+1
                copy_from = track
                break
    return copy_from,insert_point

def copy_track(data,copy_from,insert_point,source_type='filtered'):
    new_track = {}
    for el in copy_from:
        if el == 'key':
            new_track[el] = ('I/D ' + args.strain_name_to) if source_type == 'indels' else args.strain_name_to
        elif el == 'label':
            new_track[el] = (args.strain_symbol_to + '_VCF_INDELS') if source_type == 'indels' else (args.strain_symbol_to + '_VCF')
        elif el == 'urlTemplate':
            new_track[el] = copy_from[el].replace(args.strain_from, args.strain_symbol_to)
        else:
            new_track[el] = copy_from[el]

    data['tracks'].insert(insert_point, new_track)


copy_from_filtered,insert_point_filtered = find_source_track(data_in)

copy_from_indels,insert_point_indels = find_source_track(data_in,source_type='indels')

if copy_from_filtered is None:
    print('template to copy from not found for filtered: ',args.strain_from)
else:
    copy_track(data_out,copy_from_filtered,insert_point_filtered)

if copy_from_indels is None:
    print('template to copy from not found for indels: ',args.strain_from)
else:
    copy_track(data_out,copy_from_indels,insert_point_indels,source_type='indels')



for track in data_out['tracks']:
    print(track)

with open(args.file_name, 'w') as f:
    json.dump(data_out,f,indent=4)











