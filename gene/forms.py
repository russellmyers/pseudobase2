'''Form handlers for the gene application.'''

import re

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django import forms

from common.models import Species
from gene.models import Gene


class BatchFileField(forms.FileField):
    '''A field that handles the submission of a "batch gene" file.'''

    def to_python(self, value):
        '''Process a "batch gene" file to extract the relevant values.

        Returns a tuple of the e-mail address of the submitter and a list of 
        the gene symbols that appear in the file.

        '''
      
        submitter_email = None
        genes = list()
        try:
            for line in value:
                if '@' in line:
                    try:
                        validate_email(line.strip())
                        submitter_email = line.strip()
                        continue
                    except ValidationError:
                        # An invalid e-mail address is the same as none.
                        pass
                genes.append(line)
        except TypeError:
            # This might happen if the batch file field isn't specified.
            # Validation is handled later.
            pass
        return (submitter_email, genes)

    def validate(self, value):
        '''Validate that value has all the required data after processing.'''
        
        if value[1] and value[0] is None:
            raise forms.ValidationError(
              'Batch file must contain a valid e-mail address.')
        return value


class SearchForm(forms.Form):
    '''A form that handles searching by gene (and "batch gene").'''

    hold_msg = 'Hold down "Control", or "Command" on a Mac, to select more than one.'

    species = forms.ModelMultipleChoiceField(queryset=Species.objects.all(),
      widget=forms.SelectMultiple(
        attrs={'class': 'form-control form-control-sm col-9','style':'font-size:90%;', 'id': 'gene_species_id' }),
      error_messages={'required': 'At least one species must be selected.'})

    species.help_text = species.help_text.replace(hold_msg, '')  
    species.help_text = '<span class = "help_text">Select one or more species</span>'

  
    gene = forms.CharField(max_length=255, required=False,
        #Added widget for ootstrap
        widget=forms.TextInput(
        attrs={'class': 'form-control form-control-sm col-9', 'placeholder':'eg GA26895'}),
      help_text='<div class="mt-0 pt-0 help_text_sm">Supported formats:<br />&nbsp;&nbsp;'
        'Gene name (e.g. atl), &nbsp;&nbsp;GA ID (e.g. GA26895)'
        '&nbsp;&nbsp;CG ID (e.g. CG10064), &nbsp;&nbsp;<br />GLEANR ID (e.g. '
        'GLEANR_4729)&nbsp;&nbsp;FlyBase ID (e.g. FBgn0248267)</div>')

    gene_batch_file = BatchFileField(required=False,
        #Added widget for ootstrap
        widget=forms.FileInput(
        attrs={'class': 'form-control-file col-9'}),                               
      help_text='<div class="mt-0 pt-0 help_text">Example gene batch file: <a '
        'href="/static/examples/gene_batch_example.html">gene_batch_example'
        '</a></div>')

    def clean(self):
        '''Clean the submitted form data and handle high level validation.'''
      
        # Let the parent class handle the initial data cleaning process.
        cleaned_data = super(SearchForm, self).clean()
        valid_genes = False
    
        if 'gene' in cleaned_data and cleaned_data['gene']:
            valid_genes = True
          
        if 'gene_batch_file' in cleaned_data and \
          cleaned_data['gene_batch_file'][0]:
            valid_genes = True
            
        if not valid_genes:
            raise forms.ValidationError(
              'A gene symbol or batch file must be provided.')
    
        # Always return the full collection of cleaned data.
        return cleaned_data
