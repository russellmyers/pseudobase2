# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding field 'GeneBatchProcess.show_aligned'
        db.add_column(u'gene_genebatchprocess', 'show_aligned',
                      self.gf('django.db.models.fields.BooleanField')(default=False),
                      keep_default=False)


    def backwards(self, orm):
        # Deleting field 'GeneBatchProcess.show_aligned'
        db.delete_column(u'gene_genebatchprocess', 'show_aligned')


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
        u'gene.cds': {
            'Meta': {'object_name': 'CDS'},
            'end_position': ('django.db.models.fields.PositiveIntegerField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'mRNA': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['gene.MRNA']"}),
            'num': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'start_position': ('django.db.models.fields.PositiveIntegerField', [], {})
        },
        u'gene.gene': {
            'Meta': {'ordering': "('strain__species__pk', 'strain__name')", 'object_name': 'Gene'},
            'bases': ('django.db.models.fields.TextField', [], {}),
            'chromosome': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['common.Chromosome']"}),
            'end_position': ('django.db.models.fields.PositiveIntegerField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'import_code': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'start_position': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'strain': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['common.Strain']"}),
            'strand': ('django.db.models.fields.CharField', [], {'max_length': '1'})
        },
        u'gene.genebatchprocess': {
            'Meta': {'object_name': 'GeneBatchProcess'},
            'batch_end': ('django.db.models.fields.DateTimeField', [], {'null': 'True'}),
            'batch_start': ('django.db.models.fields.DateTimeField', [], {'null': 'True'}),
            'batch_status': ('django.db.models.fields.CharField', [], {'default': "'P'", 'max_length': '1', 'db_index': 'True'}),
            'delivery_tag': ('django.db.models.fields.CharField', [], {'max_length': '32', 'null': 'True'}),
            'expiration': ('django.db.models.fields.DateTimeField', [], {'null': 'True'}),
            'failed_symbols': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True'}),
            'final_report': ('django.db.models.fields.TextField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'original_request': ('django.db.models.fields.TextField', [], {}),
            'original_species': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'show_aligned': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'submitted_at': ('django.db.models.fields.DateTimeField', [], {}),
            'submitter_email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'null': 'True'}),
            'total_symbols': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True'})
        },
        u'gene.geneimportlog': {
            'Meta': {'object_name': 'GeneImportLog'},
            'end': ('django.db.models.fields.DateTimeField', [], {}),
            'file_path': ('django.db.models.fields.CharField', [], {'max_length': '1024'}),
            'gene_count': ('django.db.models.fields.PositiveIntegerField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'run_microseconds': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'start': ('django.db.models.fields.DateTimeField', [], {})
        },
        u'gene.genesymbol': {
            'Meta': {'object_name': 'GeneSymbol'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'symbol': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'translations': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'translations_rel_+'", 'to': u"orm['gene.GeneSymbol']"})
        },
        u'gene.genesymbolimportlog': {
            'Meta': {'object_name': 'GeneSymbolImportLog'},
            'end': ('django.db.models.fields.DateTimeField', [], {}),
            'file_path': ('django.db.models.fields.CharField', [], {'max_length': '1024'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'run_microseconds': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'start': ('django.db.models.fields.DateTimeField', [], {}),
            'symbol_count': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'translation_count': ('django.db.models.fields.PositiveIntegerField', [], {})
        },
        u'gene.mrna': {
            'Meta': {'object_name': 'MRNA'},
            'gene': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['gene.Gene']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'})
        }
    }

    complete_apps = ['gene']