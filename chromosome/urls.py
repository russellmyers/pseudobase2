'''ALl URL definitions and configuration for the pseudobase project.'''


from django.conf.urls import patterns, url

urlpatterns = patterns('',
  # The main index page

  url(r'^preprocessold/$', 'chromosome.views.preprocess_files_old', name='preprocessold'),

  url(r'^preprocess/(?P<fname>.+)/(?P<pre>.+)/(?P<subdir>.+)/(?P<type>.+)/(?P<verbose>.+)/info/$', 'chromosome.views._get_file_info', name='preprocessfileinfo'),

  url(r'^import/$','chromosome.views.import_files',name='import'),
   
  url(r'^import/delchr/$','chromosome.views._delete_latest',name='dellatest'),
  
   url(r'^import/(?P<fname>.+)/info/$','chromosome.views._get_file_info',name='importfileinfo'),
  
  url(r'^import/progress/$','chromosome.views.import_progress',name='importprogress'),
   
  url(r'^import/(?P<fname>.+)/$','chromosome.views.import_file',name='importfile'),

  url(r'^audit/$', 'chromosome.views.audit', name='audit'),

  url(r'^preprocess/$','chromosome.views.preprocess',name='preprocess'),

  url(r'^preprocess/progress/$','chromosome.views.preprocess_progress',name='preprocessprogress'),
                       )


