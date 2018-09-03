# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'ChromosomeBase'
        db.create_table(u'chromosome_chromosomebase', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('strain', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['common.Strain'])),
            ('chromosome', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['common.Chromosome'])),
            ('start_position', self.gf('django.db.models.fields.PositiveIntegerField')()),
            ('end_position', self.gf('django.db.models.fields.PositiveIntegerField')()),
            ('file_tag', self.gf('django.db.models.fields.CharField')(max_length=32)),
        ))
        db.send_create_signal(u'chromosome', ['ChromosomeBase'])

        # Adding model 'ChromosomeImportLog'
        db.create_table(u'chromosome_chromosomeimportlog', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('start', self.gf('django.db.models.fields.DateTimeField')()),
            ('end', self.gf('django.db.models.fields.DateTimeField')()),
            ('run_microseconds', self.gf('django.db.models.fields.PositiveIntegerField')()),
            ('file_path', self.gf('django.db.models.fields.CharField')(max_length=1024)),
            ('base_count', self.gf('django.db.models.fields.PositiveIntegerField')()),
            ('clip_count', self.gf('django.db.models.fields.PositiveIntegerField')()),
        ))
        db.send_create_signal(u'chromosome', ['ChromosomeImportLog'])


    def backwards(self, orm):
        # Deleting model 'ChromosomeBase'
        db.delete_table(u'chromosome_chromosomebase')

        # Deleting model 'ChromosomeImportLog'
        db.delete_table(u'chromosome_chromosomeimportlog')


    models = {
        u'chromosome.chromosomebase': {
            'Meta': {'ordering': "('strain__species__pk', 'chromosome__name', 'strain__name')", 'object_name': 'ChromosomeBase'},
            'chromosome': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['common.Chromosome']"}),
            'end_position': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'file_tag': ('django.db.models.fields.CharField', [], {'max_length': '32'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'start_position': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'strain': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['common.Strain']"})
        },
        u'chromosome.chromosomeimportlog': {
            'Meta': {'object_name': 'ChromosomeImportLog'},
            'base_count': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'clip_count': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'end': ('django.db.models.fields.DateTimeField', [], {}),
            'file_path': ('django.db.models.fields.CharField', [], {'max_length': '1024'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'run_microseconds': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'start': ('django.db.models.fields.DateTimeField', [], {})
        },
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

    complete_apps = ['chromosome']