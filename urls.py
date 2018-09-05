'''ALl URL definitions and configuration for the pseudobase project.'''

from django.conf import settings
from django.conf.urls import include, patterns, url
from django.conf.urls.static import static
from django.contrib import admin


admin.autodiscover()

urlpatterns = patterns('',
  # The main index page
 
   url(r'^$', 'common.views.index',name='index'),
  
   url(r'^info/$','common.views.info',name='info'),

  
  # The page handling file deliveries
  (r'^delivery/(.+)$', 'common.views.delivery'),
  
  # Uncomment the admin/doc line below to enable admin documentation:
  # (r'^admin/doc/', include('django.contrib.admindocs.urls')),

  # The administrative pages
  (r'^admin/', include(admin.site.urls)),
)

# Serve media/ files when DEBUG mode is enabled.
urlpatterns += static(
  settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
