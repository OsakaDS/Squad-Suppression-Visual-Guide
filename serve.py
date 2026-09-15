#!/usr/bin/env python3
"""Serve docs/ on the LAN. Gzips on the fly (1.3 MB -> ~780 KB) and sets a UTF-8 charset.

    python3 serve.py            # port 8080, reachable from other machines
    python3 serve.py 9000       # different port
"""
import gzip, io, os, socket, sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'docs')
ZIPPABLE = ('text/html', 'text/css', 'application/javascript', 'application/json',
            'image/svg+xml', 'text/plain', 'text/csv')

class Handler(SimpleHTTPRequestHandler):
    def guess_type(self, path):
        t = super().guess_type(path)
        return t + '; charset=utf-8' if t.split(';')[0] in ZIPPABLE else t

    def send_head(self):
        path = self.translate_path(self.path)
        if os.path.isdir(path):
            path = os.path.join(path, 'index.html')
        if not os.path.isfile(path):
            return super().send_head()
        ctype = self.guess_type(path)
        body = open(path, 'rb').read()
        enc = None
        if ctype.split(';')[0] in ZIPPABLE and 'gzip' in self.headers.get('Accept-Encoding', ''):
            buf = io.BytesIO()
            with gzip.GzipFile(fileobj=buf, mode='wb', compresslevel=6, mtime=0) as g:
                g.write(body)
            body, enc = buf.getvalue(), 'gzip'
        self.send_response(200)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        if enc: self.send_header('Content-Encoding', enc)
        self.send_header('Cache-Control', 'public, max-age=300')
        self.end_headers()
        return io.BytesIO(body)

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))

def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('192.0.2.1', 80)); return s.getsockname()[0]
    except Exception:
        return '127.0.0.1'
    finally:
        s.close()

if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    srv = ThreadingHTTPServer(('0.0.0.0', port), partial(Handler, directory=ROOT))
    print(f"Serving {ROOT}")
    print(f"  this machine   http://localhost:{port}")
    print(f"  anyone on LAN  http://{lan_ip()}:{port}")
    print("Ctrl-C to stop.")
    try: srv.serve_forever()
    except KeyboardInterrupt: print("\nstopped")
