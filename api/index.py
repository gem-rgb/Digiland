import traceback
import sys

# Fallback handler
def fallback_handler(environ, start_response):
    start_response("500 Internal Server Error", [("Content-Type", "text/plain")])
    return [b"Fallback Handler: Import/setup failed."]

# Top-level declarations for Vercel AST parser
application = fallback_handler
app = fallback_handler
handler = fallback_handler

try:
    from wsgi import application as _application
    
    class TracebackMiddleware:
        def __init__(self, app):
            self.app = app
        def __call__(self, environ, start_response):
            # Keep the legacy marketplace URL working even if an older cached
            # Django module is loaded by a serverless worker.
            if environ.get('PATH_INFO', '').rstrip('/') == '/marketplace':
                location = '/parcels/'
                if environ.get('QUERY_STRING'):
                    location += '?' + environ['QUERY_STRING']
                start_response('302 Found', [('Location', location), ('Content-Type', 'text/plain')])
                return [b'Redirecting to the marketplace.']
            try:
                return self.app(environ, start_response)
            except Exception as e:
                tb = traceback.format_exc()
                start_response("500 Internal Server Error", [("Content-Type", "text/plain")])
                return [f"Runtime crash:\n{tb}".encode("utf-8")]
    
    real_app = TracebackMiddleware(_application)
    application = real_app
    app = real_app
    handler = real_app

except Exception as e:
    tb = traceback.format_exc()
    def error_handler(environ, start_response):
        start_response("500 Internal Server Error", [("Content-Type", "text/plain")])
        return [f"Import failed:\n{tb}".encode("utf-8")]
    application = error_handler
    app = error_handler
    handler = error_handler
