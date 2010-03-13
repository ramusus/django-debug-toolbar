"""
Debug Toolbar middleware
"""
from django.conf import settings
from django.conf.urls.defaults import patterns, url, include
from django.core.urlresolvers import get_resolver
from django.http import HttpResponseRedirect
from django.shortcuts import render_to_response
from django.utils.encoding import smart_unicode

from debug_toolbar.toolbar.loader import DebugToolbar


_HTML_TYPES = ('text/html', 'application/xhtml+xml')

DEBUG_TOOLBAR_CONFIG = getattr(settings, "DEBUG_TOOLBAR_CONFIG", {})

def replace_insensitive(request, string, target, replacement):
    """
    Similar to string.replace() but is case insensitive
    Code borrowed from: http://forums.devshed.com/python-programming-11/case-insensitive-string-replace-490921.html
    """

    no_case = string.lower()
    index = no_case.rfind(target.lower())
    # if ajax request or request by testserver => return without toolbar
    if request.is_ajax() or request.META.get('SERVER_NAME', None) == 'testserver':
        return string
    elif index >= 0:
        return string[:index] + replacement + string[index + len(target):]
    else: # added toolbar for introspecting ajax requests with any content in new window
        return string + replacement

class DebugToolbarMiddleware(object):
    """
    Middleware to set up Debug Toolbar on incoming request and render toolbar
    on outgoing response.
    """
    PREFIX = '__debug__'
    panel_classes = [
        'debug_toolbar.panels.version.VersionDebugPanel',
        'debug_toolbar.panels.timer.TimerDebugPanel',
        'debug_toolbar.panels.settings_vars.SettingsVarsDebugPanel',
        'debug_toolbar.panels.headers.HeaderDebugPanel',
        'debug_toolbar.panels.request_vars.RequestVarsDebugPanel',
        'debug_toolbar.panels.sql.SQLDebugPanel',
        'debug_toolbar.panels.template.TemplateDebugPanel',
        #'debug_toolbar.panels.cache.CacheDebugPanel',
        'debug_toolbar.panels.signals.SignalDebugPanel',
        'debug_toolbar.panels.logger.LoggingPanel',
    ]


    def __init__(self):
        self.debug_toolbars = {}

        self.show_toolbar = DEBUG_TOOLBAR_CONFIG.get(
            'SHOW_TOOLBAR_CALLBACK', self._show_toolbar)

        tag = DEBUG_TOOLBAR_CONFIG.get('TAG', 'body')
        self.tag = u'</' + tag + u'>'

        urlconfs = DEBUG_TOOLBAR_CONFIG.get("urlconfs", []) + [settings.ROOT_URLCONF]
        self.panel_classes = DEBUG_TOOLBAR_CONFIG.get("DEBUG_TOOLBAR_PANELS",
            self.panel_classes)
        for urlconf in urlconfs:
            resolver = get_resolver(urlconf)
            if hasattr(resolver.urlconf_module, "urlpatterns"):
                resolver.urlconf_module.urlpatterns += self.urls
            else:
                resolver.urlconf_module += self.urls

    def _show_toolbar(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR', None)
        if x_forwarded_for:
            remote_addr = x_forwarded_for.split(',')[0].strip()
        else:
            remote_addr = request.META.get('REMOTE_ADDR', None)
        if (not remote_addr in settings.INTERNAL_IPS or not settings.DEBUG
            or (request.is_ajax() and not self.PREFIX in request.path)):
            return False
        return True

    def process_request(self, request):
        if self.show_toolbar(request):
            self.debug_toolbars[request] = DebugToolbar(request, self.panel_classes)
            for panel in self.debug_toolbars[request].panels:
                panel.process_request(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        if request in self.debug_toolbars:
            for panel in self.debug_toolbars[request].panels:
                panel.process_view(request, view_func, view_args, view_kwargs)

    def process_response(self, request, response):
        if request not in self.debug_toolbars:
            return response
        if self.debug_toolbars[request].config['INTERCEPT_REDIRECTS']:
            if isinstance(response, HttpResponseRedirect):
                redirect_to = response.get('Location', None)
                if redirect_to:
                    response = render_to_response(
                        'debug_toolbar/redirect.html',
                        {'redirect_to': redirect_to}
                    )
        if response.status_code == 200:
            toolbar = self.debug_toolbars[request]
            for panel in toolbar.panels:
                panel.process_response(request, response)
            if response['Content-Type'].split(';')[0] in _HTML_TYPES:
                response.content = replace_insensitive(
                    request,
                    smart_unicode(response.content),
                    self.tag,
                    smart_unicode(toolbar.render_toolbar() + self.tag)
                )
            if 'Content-Length' in response:
                response['Content-Length'] = len(response.content)
        del self.debug_toolbars[request]
        return response

    @property
    def urls(self):
        return self.get_urls()

    def get_urls(self):
        return patterns("",
            url(r"^%s/" % self.PREFIX, include(patterns("debug_toolbar.views",
                url(r'^m/(.*)$', 'debug_media'),
                url(r'^sql_select/$', 'sql_select', name='sql_select'),
                url(r'^sql_explain/$', 'sql_explain', name='sql_explain'),
                url(r'^sql_profile/$', 'sql_profile', name='sql_profile'),
                url(r'^template_source/$', 'template_source', name='template_source'),
            )))
        )
