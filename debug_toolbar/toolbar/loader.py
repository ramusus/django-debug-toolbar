"""
The main DebugToolbar class that loads and renders the Toolbar.
"""
import sys

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.template.loader import render_to_string


class DebugToolbar(object):
    def __init__(self, request, panel_classes):
        self.request = request
        self.panels = []
        base_url = self.request.META.get('SCRIPT_NAME', '')
        self.config = {
            'INTERCEPT_REDIRECTS': True,
            'MEDIA_URL': u'%s/__debug__/m/' % base_url
        }
        # Check if settings has a DEBUG_TOOLBAR_CONFIG and updated config
        self.config.update(getattr(settings, 'DEBUG_TOOLBAR_CONFIG', {}))
        self.template_context = {
            'BASE_URL': base_url, # for backwards compatibility
            'DEBUG_TOOLBAR_MEDIA_URL': self.config.get('MEDIA_URL'),
        }
        self.load_panels(panel_classes)

    def load_panels(self, panel_classes):
        """
        Populate debug panels
        """
        # Check if settings has a DEBUG_TOOLBAR_PANELS, otherwise use default
        for panel_path in panel_classes:
            try:
                dot = panel_path.rindex('.')
            except ValueError:
                raise ImproperlyConfigured("%s isn't a debug panel module" %
                    panel_path)
            panel_module, panel_classname = panel_path[:dot], panel_path[dot+1:]
            try:
                __import__(panel_module)
                mod = sys.modules[panel_module]
            except ImportError, e:
                raise ImproperlyConfigured('Error importing debug panel %s: "%s"' % 
                    (panel_module, e))
            try:
                panel_class = getattr(mod, panel_classname)
            except AttributeError:
                raise ImproperlyConfigured('Toolbar Panel module "%s" does not '
                    'define a "%s" class' % (panel_module, panel_classname))

            panel_instance = panel_class(context=self.template_context)

            self.panels.append(panel_instance)

    def render_toolbar(self):
        """
        Renders the overall Toolbar with panels inside.
        """
        context = self.template_context.copy()
        context['panels'] = self.panels

        return render_to_string('debug_toolbar/base.html', context)
