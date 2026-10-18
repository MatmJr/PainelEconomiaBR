"""
Serve a pasta site/ localmente com os mesmos cabeçalhos definidos em
netlify.toml (inclusive a Content-Security-Policy) e a mesma página 404,
para testar o site como ele vai rodar no Netlify:

    python servir_site.py          # http://localhost:8000
    python servir_site.py 8080
"""

import fnmatch
import sys
import tomllib
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
PASTA_SITE = RAIZ / "site"
REGRAS = tomllib.loads((RAIZ / "netlify.toml").read_text(encoding="utf-8")).get("headers", [])


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        caminho = self.path.split("?")[0]
        for regra in REGRAS:
            if fnmatch.fnmatch(caminho, regra["for"]):
                for nome, valor in regra["values"].items():
                    self.send_header(nome, valor)
        super().end_headers()

    def send_error(self, code, message=None, explain=None):
        pagina = PASTA_SITE / "404.html"
        if code == 404 and pagina.exists():
            corpo = pagina.read_bytes()
            self.send_response(404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)
            return
        super().send_error(code, message, explain)


if __name__ == "__main__":
    porta = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    servidor = ThreadingHTTPServer(("localhost", porta), partial(Handler, directory=str(PASTA_SITE)))
    print(f"Site em http://localhost:{porta} (Ctrl+C para parar)")
    servidor.serve_forever()
