
# Python utilities

  
- vcf_split
  - Splits raw vcf files provided by Noor lab into separate files per chromosome,and moves these to "pending_import" folder in preparation for chromosome/import
  - creates filtered files for JBrowse (ie containing SNPs and Indels relevant to strain only)
  - creates "indels only" files for JBrowse  

- prepare_vcf_all
  -  run commands to add indexes to JBrowse track files (required by JBrowse) for filtered and indel files created above
  
  
- add_track.py
  - Helper to add new track  config to trackList.json file. Used to add tracks for files created above
  
  
> Deprecated files:
>>   prepare_vcf (now in prepare_vcf_all)<br>
>> prepare_vcf_indels_only (now in prepare_vcf_all)<br>
>> vcf_move_to_pending_import   (now in vcf_split) 