# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'DocumentationType'
        db.create_table(u'common_documentationtype', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('code', self.gf('django.db.models.fields.CharField')(max_length=50)),
            ('description', self.gf('django.db.models.fields.CharField')(max_length=255)),
        ))
        db.send_create_signal(u'common', ['DocumentationType'])

        # Adding model 'Documentation'
        db.create_table(u'common_documentation', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('doctype', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['common.DocumentationType'])),
            ('sequence', self.gf('django.db.models.fields.IntegerField')()),
            ('text', self.gf('django.db.models.fields.TextField')(blank=True)),
        ))
        db.send_create_signal(u'common', ['Documentation'])


    def backwards(self, orm):
        # Deleting model 'DocumentationType'
        db.delete_table(u'common_documentationtype')

        # Deleting model 'Documentation'
        db.delete_table(u'common_documentation')


    models = {
        u'common.chromosome': {
            'Meta': {'object_name': 'Chromosome'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'})
        },
        u'common.documentation': {
            'Meta': {'object_name': 'Documentation'},
            'doctype': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['common.DocumentationType']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'sequence': ('django.db.models.fields.IntegerField', [], {}),
            'text': ('django.db.models.fields.TextField', [], {'blank': 'True'})
        },
        u'common.documentationtype': {
            'Meta': {'object_name': 'DocumentationType'},
            'code': ('django.db.models.fields.CharField', [], {'max_length': '50'}),
            'description': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        u'common.release': {
            'Meta': {'object_name': 'Release'},
            'description': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '20'})
        },
        u'common.species': {
            'Meta': {'object_name': 'Species'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'symbol': ('django.db.models.fields.CharField', [], {'max_length': '16'})
        },
        u'common.strain': {
            'Meta': {'ordering': "('release__name', 'species__name', '-is_reference')", 'object_name': 'Strain'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_reference': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'release': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['common.Release']", 'null': 'True'}),
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