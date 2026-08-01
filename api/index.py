import os
import sys
import traceback

# Ensure repository root and Django project directory are on sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

try:
    from deploy_bootstrap import bootstrap
    bootstrap()
except Exception:
    pass

# Fallback handler
def fallback_handler(environ, start_response):
    if environ.get('PATH_INFO', '').startswith('/api/'):
        start_response("500 Internal Server Error", [("Content-Type", "application/json")])
        return [b'{"error": "Service temporarily unavailable. Please try again."}']
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
            path_info = (environ.get('PATH_INFO', '') or '').rstrip('/')
            if path_info == '/marketplace':
                location = '/parcels/'
                if environ.get('QUERY_STRING'):
                    location += '?' + environ['QUERY_STRING']
                start_response('302 Found', [('Location', location), ('Content-Type', 'text/plain')])
                return [b'Redirecting to the marketplace.']
            try:
                return self.app(environ, start_response)
            except Exception as e:
                tb = traceback.format_exc()
                if path_info.startswith('/api/'):
                    start_response("500 Internal Server Error", [("Content-Type", "application/json")])
                    return [b'{"error": "An unexpected error occurred. Please try again."}']
                start_response("500 Internal Server Error", [("Content-Type", "text/plain")])
                return [f"Runtime crash:\n{tb}".encode("utf-8")]
    
    real_app = TracebackMiddleware(_application)
    application = real_app
    app = real_app
    handler = real_app

except Exception as e:
    tb = traceback.format_exc()
    def error_handler(environ, start_response):
        if (environ.get('PATH_INFO', '') or '').startswith('/api/'):
            start_response("500 Internal Server Error", [("Content-Type", "application/json")])
            return [b'{"error": "Application initialization failed. Please try again."}']
        start_response("500 Internal Server Error", [("Content-Type", "text/plain")])
        return [f"Import failed:\n{tb}".encode("utf-8")]
    application = error_handler
    app = error_handler
    handler = error_handler

