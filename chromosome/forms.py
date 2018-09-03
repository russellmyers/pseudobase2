'''Forms and assocated configuration for the chromosome application.'''

import re

from django import forms

from common.models import Species, Chromosome


class PositionRangeField(forms.CharField):
    '''A field that handles a range of positions.'''
  
    def to_python(self, value):
        '''Normalize value to a tuple with the start and end positions.'''

        positions = None

        if not value:
            raise forms.ValidationError(
              'A range of positions must be provided.')

        try:
            # See if the position data is a single number.
            # If it is, assume the user just wants a single base.
            positions = (int(value), int(value))
        except ValueError:
            # The position data is not a valid integer.
            pass

        # If a valid range[1] is specified, then split the data into the
        # appropriate individual start and end positions.
        #
        # [1] Two numbers (optionally including periods or commas) separated 
        # by either a single non-numeric (excluding periods and commas)
        # character or two or more non-numeric characters (including periods
        # and commas) in a sequence.
        position_match = re.compile(
          r'^([0-9.,]+[0-9]+)([^0-9,.]|[^0-9]{2,})([0-9]+[0-9.,]+)$').match
        position_sub = re.compile(r'\D').sub
        p_m = position_match(value)
        if p_m:
            try:
                start = position_sub('', p_m.group(1))
                end = position_sub('', p_m.group(3))
                positions = (int(start), int(end))
            except ValueError:
                # An error is raised later if the range can't be parsed.
                pass

        if not positions:
            raise forms.ValidationError('Position range is invalid.')

        return positions

    def validate(self, value):
        '''Validate that value consists of a valid range of positions.'''

        # Use the parent's handling of required fields, etc.
        super(PositionRangeField, self).validate(value)
    
        start_position = value[0]
        end_position = value[1]
    
        # Make sure the range is logically valid.
        if end_position < start_position:
            raise forms.ValidationError(
              'End position must be greater than or equal to start position.')

        return value


class SearchForm(forms.Form):
    '''A form that handles searching by chromosome.'''
    
    species = forms.ModelMultipleChoiceField(queryset=Species.objects.all(),
      widget=forms.SelectMultiple(
        attrs={'size': '4', 'id': 'chromosome_species_id'}),
      error_messages={'required': 'At least one species must be selected.'})
  
    chromosome = forms.ModelChoiceField(queryset=Chromosome.objects.all(),
      error_messages={'required': 'A chromosome must be selected.'})
  
    position = PositionRangeField(max_length=20,help_text=\
      '<span class="help_text">Format: &lt;start&gt;..&lt;end&gt;</span>')
