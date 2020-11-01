# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'StrainCollectionInfo'
        db.create_table(u'common_straincollectioninfo', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('strain', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['common.Strain'], unique=True, on_delete=models.PROTECT)),
            ('year', self.gf('django.db.models.fields.PositiveIntegerField')(null=True, blank=True)),
            ('info', self.gf('django.db.models.fields.TextField')(blank=True)),
        ))
        db.send_create_signal(u'common', ['StrainCollectionInfo'])


    def backwards(self, orm):
        # Deleting model 'StrainCollectionInfo'
        db.delete_table(u'common_straincollectioninfo')


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
        },
        u'common.straincollectioninfo': {
            'Meta': {'object_name': 'StrainCollectionInfo'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'info': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'strain': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['common.Strain']", 'unique': 'True', 'on_delete': 'models.PROTECT'}),
            'year': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True', 'blank': 'True'})
        },
        u'common.strainsymbol': {
            'Meta': {'object_name': 'StrainSymbol'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'strain': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['common.Strain']"}),
            'symbol': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '255'})
        }
    }

    complete_apps = ['common']