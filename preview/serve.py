"""Loopback-only static preview. Only explicitly mapped saved documents are exposed."""
import argparse
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DIST = HERE / 'dist'
ROUTES = json.loads((HERE / 'document_routes.json').read_text(encoding='utf-8'))


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIST), **kwargs)

    def translate_path(self, path):
        route = unquote(urlsplit(path).path)
        if route in ROUTES:
            target = (ROOT / ROUTES[route]).resolve()
            if not target.is_relative_to((ROOT / 'experiments' / 'samples').resolve()):
                return str(DIST / '__unavailable__')
            return str(target)
        return super().translate_path(path)

    def list_directory(self, path):
        self.send_error(404, 'No directory listing')
        return None

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; object-src 'none'")
        super().end_headers()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    print(f'FINN local preview: http://127.0.0.1:{args.port}', flush=True)
    print('Saved, dated samples only. Stop with Ctrl+C.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
