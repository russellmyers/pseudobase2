# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import DataMigration
from django.db import models

class Migration(DataMigration):

    def forwards(self, orm):
        '''Define the reference strain.'''

        ref_strains = orm.Strain.objects.filter(
          name='Mesa Verde, CO 2-25 reference line')
        for r_s in ref_strains:
            r_s.is_reference = True
            r_s.save()

    def backwards(self, orm):
        '''Roll back the reference strain definition.'''
        
        ref_strains = orm.Strain.objects.filter(
          name='Mesa Verde, CO 2-25 reference line')
        for r_s in ref_strains:
            r_s.is_reference = False
            r_s.save()

    models = {
        u'common.chromosome': {
            'Meta': {'object_name': 'Chromosome'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'})
        },
        u'common.species': {
            'Meta': {'object_name': 'Species'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'symbol': ('django.db.models.fields.CharField', [], {'max_length': '16'})
        },
        u'common.strain': {
            'Meta': {'object_name': 'Strain'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_reference': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'species': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['common.Species']"})
        }
    }

    complete_apps = ['common']
    symmetrical = True
