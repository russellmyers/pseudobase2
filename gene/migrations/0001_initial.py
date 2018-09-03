# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'Gene'
        db.create_table(u'gene_gene', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('strain', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['common.Strain'])),
            ('chromosome', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['common.Chromosome'])),
            ('start_position', self.gf('django.db.models.fields.PositiveIntegerField')()),
            ('end_position', self.gf('django.db.models.fields.PositiveIntegerField')()),
            ('import_code', self.gf('django.db.models.fields.CharField')(max_length=255, db_index=True)),
            ('bases', self.gf('django.db.models.fields.TextField')()),
        ))
        db.send_create_signal(u'gene', ['Gene'])

        # Adding model 'GeneSymbol'
        db.create_table(u'gene_genesymbol', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('symbol', self.gf('django.db.models.fields.CharField')(max_length=255)),
        ))
        db.send_create_signal(u'gene', ['GeneSymbol'])

        # Adding M2M table for field translations on 'GeneSymbol'
        db.create_table(u'gene_genesymbol_translations', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('from_genesymbol', models.ForeignKey(orm[u'gene.genesymbol'], null=False)),
            ('to_genesymbol', models.ForeignKey(orm[u'gene.genesymbol'], null=False))
        ))
        db.create_unique(u'gene_genesymbol_translations', ['from_genesymbol_id', 'to_genesymbol_id'])

        # Adding model 'GeneImportLog'
        db.create_table(u'gene_geneimportlog', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('start', self.gf('django.db.models.fields.DateTimeField')()),
            ('end', self.gf('django.db.models.fields.DateTimeField')()),
            ('run_microseconds', self.gf('django.db.models.fields.PositiveIntegerField')()),
            ('file_path', self.gf('django.db.models.fields.CharField')(max_length=1024)),
            ('gene_count', self.gf('django.db.models.fields.PositiveIntegerField')()),
        ))
        db.send_create_signal(u'gene', ['GeneImportLog'])

        # Adding model 'GeneSymbolImportLog'
        db.create_table(u'gene_genesymbolimportlog', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('start', self.gf('django.db.models.fields.DateTimeField')()),
            ('end', self.gf('django.db.models.fields.DateTimeField')()),
            ('run_microseconds', self.gf('django.db.models.fields.PositiveIntegerField')()),
            ('file_path', self.gf('django.db.models.fields.CharField')(max_length=1024)),
            ('symbol_count', self.gf('django.db.models.fields.PositiveIntegerField')()),
            ('translation_count', self.gf('django.db.models.fields.PositiveIntegerField')()),
        ))
        db.send_create_signal(u'gene', ['GeneSymbolImportLog'])

        # Adding model 'GeneBatchProcess'
        db.create_table(u'gene_genebatchprocess', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('submitter_email', self.gf('django.db.models.fields.EmailField')(max_length=75, null=True)),
            ('submitted_at', self.gf('django.db.models.fields.DateTimeField')()),
            ('batch_status', self.gf('django.db.models.fields.CharField')(default='P', max_length=1, db_index=True)),
            ('batch_start', self.gf('django.db.models.fields.DateTimeField')(null=True)),
            ('batch_end', self.gf('django.db.models.fields.DateTimeField')(null=True)),
            ('final_report', self.gf('django.db.models.fields.TextField')()),
            ('delivery_tag', self.gf('django.db.models.fields.CharField')(max_length=32, null=True)),
            ('expiration', self.gf('django.db.models.fields.DateTimeField')(null=True)),
            ('original_species', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('original_request', self.gf('django.db.models.fields.TextField')()),
            ('total_symbols', self.gf('django.db.models.fields.PositiveIntegerField')(null=True)),
            ('failed_symbols', self.gf('django.db.models.fields.PositiveIntegerField')(null=True)),
        ))
        db.send_create_signal(u'gene', ['GeneBatchProcess'])


    def backwards(self, orm):
        # Deleting model 'Gene'
        db.delete_table(u'gene_gene')

        # Deleting model 'GeneSymbol'
        db.delete_table(u'gene_genesymbol')

        # Removing M2M table for field translations on 'GeneSymbol'
        db.delete_table('gene_genesymbol_translations')

        # Deleting model 'GeneImportLog'
        db.delete_table(u'gene_geneimportlog')

        # Deleting model 'GeneSymbolImportLog'
        db.delete_table(u'gene_genesymbolimportlog')

        # Deleting model 'GeneBatchProcess'
        db.delete_table(u'gene_genebatchprocess')


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
        u'gene.gene': {
            'Meta': {'ordering': "('strain__species__pk', 'strain__name')", 'object_name': 'Gene'},
            'bases': ('django.db.models.fields.TextField', [], {}),
            'chromosome': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['common.Chromosome']"}),
            'end_position': ('django.db.models.fields.PositiveIntegerField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'import_code': ('django.db.models.fields.CharField', [], {'max_length': '255', 'db_index': 'True'}),
            'start_position': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'strain': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['common.Strain']"})
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
        }
    }

    complete_apps = ['gene']