from django.test import TestCase
from common.models import Species,Strain,StrainCollectionInfo

class SpeciesTests(TestCase):

    def setUp(self):
        try:
           Species.objects.create(name='just a test',symbol='SYM')
          
            
        except Exception as e:  
            self.fail('Species setUp test failed: ' + str(e))

    def test_text_content(self):
        try:

            species = Species.objects.all()[0]
            expected_object_name = species.name
            self.assertEquals(expected_object_name, 'just a test')
        except Exception as e:
               self.fail('Species name test failed: ' + str(e))
               
    def test_symbol_content(self):
        try:
            species = Species.objects.all()[0]
            expected_object_symbol = species.symbol
            self.assertEquals(expected_object_symbol, 'SYM')
        except Exception as e:
               self.fail('Species symbol test failed: ' + str(e))               
               
               
class StrainTests(TestCase): 
    def setUp(self):
        try:
           sp = Species.objects.create(name='just a test species',symbol='SYM')
           Strain.objects.create(name='just a test strain',species = sp)
          
            
        except Exception as e:  
            self.fail('Strain test setUp failed: ' + str(e))

    def test_strain_text(self):
        try:

            strain =  Strain.objects.all()[0]
            expected_object_name = strain.name
            col_info = strain.formatted_info
            self.assertEquals(col_info,expected_object_name) #No info object, so formatted info just strain name
               

            
            self.assertEquals(expected_object_name, 'just a test strain')
            self.assertEquals(strain.species.name,'just a test species')

            
        except Exception as e:
               self.fail('Strain text test failed: ' + str(e))

    def test_strain__with_info(self):
        try:

            strain =  Strain.objects.all()[0]
            StrainCollectionInfo.objects.create(year=1976,info='somewhere',strain=strain)
            self.assertEquals(strain.straincollectioninfo.year,1976)
            self.assertEquals(strain.straincollectioninfo.info,'somewhere')
            self.assertEquals(strain.formatted_info,'just a test strain, collected: 1976, somewhere')
            
        except Exception as e:
               self.fail('Strain info test failed: ' + str(e))