"""Serve the demo locally at http://127.0.0.1:8000/local.html

index.html is authored for Claude Artifacts (the platform adds the <!doctype>/<head> skeleton and the
`sample` capability). This wraps it in a UTF-8 skeleton for local viewing. Without the Claude runtime the
page runs the keyword stage and the keyword benchmark only.
"""
import http.server
import os
import socketserver

SITE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "site")
page = open(os.path.join(SITE, "index.html"), encoding="utf-8").read()
with open(os.path.join(SITE, "local.html"), "w", encoding="utf-8") as f:
    f.write('<!doctype html><html><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"></head><body>'
            + page + "</body></html>")
os.chdir(SITE)
with socketserver.TCPServer(("127.0.0.1", 8000), http.server.SimpleHTTPRequestHandler) as httpd:
    print("Open http://127.0.0.1:8000/local.html")
    httpd.serve_forever()
