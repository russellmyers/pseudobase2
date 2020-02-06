# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'Species'
        db.create_table(u'common_species', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('symbol', self.gf('django.db.models.fields.CharField')(max_length=16)),
        ))
        db.send_create_signal(u'common', ['Species'])

        # Adding model 'Release'
        db.create_table(u'common_release', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=20)),
            ('description', self.gf('django.db.models.fields.CharField')(max_length=255)),
        ))
        db.send_create_signal(u'common', ['Release'])

        # Adding model 'Strain'
        db.create_table(u'common_strain', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('species', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['common.Species'])),
            ('release', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['common.Release'], null=True)),
            ('is_reference', self.gf('django.db.models.fields.BooleanField')(default=False)),
        ))
        db.send_create_signal(u'common', ['Strain'])

        # Adding model 'StrainCollectionInfo'
        db.create_table(u'common_straincollectioninfo', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('strain', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['common.Strain'], unique=True, on_delete=models.PROTECT)),
            ('year', self.gf('django.db.models.fields.PositiveIntegerField')(null=True, blank=True)),
            ('info', self.gf('django.db.models.fields.TextField')(blank=True)),
        ))
        db.send_create_signal(u'common', ['StrainCollectionInfo'])

        # Adding model 'StrainSymbol'
        db.create_table(u'common_strainsymbol', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('symbol', self.gf('django.db.models.fields.CharField')(unique=True, max_length=255)),
            ('strain', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['common.Strain'])),
        ))
        db.send_create_signal(u'common', ['StrainSymbol'])

        # Adding model 'Chromosome'
        db.create_table(u'common_chromosome', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=255)),
        ))
        db.send_create_signal(u'common', ['Chromosome'])


    def backwards(self, orm):
        # Deleting model 'Species'
        db.delete_table(u'common_species')

        # Deleting model 'Release'
        db.delete_table(u'common_release')

        # Deleting model 'Strain'
        db.delete_table(u'common_strain')

        # Deleting model 'StrainCollectionInfo'
        db.delete_table(u'common_straincollectioninfo')

        # Deleting model 'StrainSymbol'
        db.delete_table(u'common_strainsymbol')

        # Deleting model 'Chromosome'
        db.delete_table(u'common_chromosome')


    models = {
        u'common.chromosome': {
            'Meta': {'object_name': 'Chromosome'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'})
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