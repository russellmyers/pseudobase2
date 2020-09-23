# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'ChromosomeBatchPreprocess'
        db.create_table(u'chromosome_chromosomebatchpreprocess', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('submitter_email', self.gf('django.db.models.fields.EmailField')(max_length=75, null=True)),
            ('submitted_at', self.gf('django.db.models.fields.DateTimeField')()),
            ('batch_status', self.gf('django.db.models.fields.CharField')(default='P', max_length=1, db_index=True)),
            ('batch_start', self.gf('django.db.models.fields.DateTimeField')(null=True)),
            ('batch_end', self.gf('django.db.models.fields.DateTimeField')(null=True)),
            ('final_report', self.gf('django.db.models.fields.TextField')()),
            ('delivery_tag', self.gf('django.db.models.fields.CharField')(max_length=32, null=True)),
            ('expiration', self.gf('django.db.models.fields.DateTimeField')(null=True)),
            ('original_request', self.gf('django.db.models.fields.TextField')()),
        ))
        db.send_create_signal(u'chromosome', ['ChromosomeBatchPreprocess'])


    def backwards(self, orm):
        # Deleting model 'ChromosomeBatchPreprocess'
        db.delete_table(u'chromosome_chromosomebatchpreprocess')


    models = {
        u'chromosome.chromosomebase': {
            'Meta': {'ordering': "('strain__release__name', 'chromosome__name', '-strain__is_reference', 'strain__name')", 'object_name': 'ChromosomeBase'},
            'chromosome': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['common.Chromosome']"}),
            'end_position': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'file_tag': ('django.db.models.fields.CharField', [], {'max_length': '32'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'start_position': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'strain': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['common.Strain']"})
        },
        u'chromosome.chromosomebatchimportlog': {
            'Meta': {'object_name': 'ChromosomeBatchImportLog'},
            'base_count': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'batch': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['chromosome.ChromosomeBatchImportProcess']"}),
            'chromebase': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['chromosome.ChromosomeBase']", 'null': 'True', 'blank': 'True'}),
            'clip_count': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'end': ('django.db.models.fields.DateTimeField', [], {}),
            'file_path': ('django.db.models.fields.CharField', [], {'max_length': '1024'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'records_read': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0', 'blank': 'True'}),
            'run_microseconds': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'start': ('django.db.models.fields.DateTimeField', [], {}),
            'status': ('django.db.models.fields.CharField', [], {'default': "'P'", 'max_length': '1', 'db_index': 'True'}),
            'vcf_meta_data': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'})
        },
        u'chromosome.chromosomebatchimportprocess': {
            'Meta': {'object_name': 'ChromosomeBatchImportProcess'},
            'batch_end': ('django.db.models.fields.DateTimeField', [], {'null': 'True'}),
            'batch_start': ('django.db.models.fields.DateTimeField', [], {'null': 'True'}),
            'batch_status': ('django.db.models.fields.CharField', [], {'default': "'P'", 'max_length': '1', 'db_index': 'True'}),
            'delivery_tag': ('django.db.models.fields.CharField', [], {'max_length': '32', 'null': 'True'}),
            'expiration': ('django.db.models.fields.DateTimeField', [], {'null': 'True'}),
            'final_report': ('django.db.models.fields.TextField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'original_request': ('django.db.models.fields.TextField', [], {}),
            'submitted_at': ('django.db.models.fields.DateTimeField', [], {}),
            'submitter_email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'null': 'True'})
        },
        u'chromosome.chromosomebatchpreprocess': {
            'Meta': {'object_name': 'ChromosomeBatchPreprocess'},
            'batch_end': ('django.db.models.fields.DateTimeField', [], {'null': 'True'}),
            'batch_start': ('django.db.models.fields.DateTimeField', [], {'null': 'True'}),
            'batch_status': ('django.db.models.fields.CharField', [], {'default': "'P'", 'max_length': '1', 'db_index': 'True'}),
            'delivery_tag': ('django.db.models.fields.CharField', [], {'max_length': '32', 'null': 'True'}),
            'expiration': ('django.db.models.fields.DateTimeField', [], {'null': 'True'}),
            'final_report': ('django.db.models.fields.TextField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'original_request': ('django.db.models.fields.TextField', [], {}),
            'submitted_at': ('django.db.models.fields.DateTimeField', [], {}),
            'submitter_email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'null': 'True'})
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
        }
    }

    complete_apps = ['chromosome']