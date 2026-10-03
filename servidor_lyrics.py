#!/usr/bin/env python3
"""Letra ao vivo: Python 3.8+, sem dependências. Use --help para opções."""
import argparse
import hmac
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

PAGE = r'''<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Letra ao vivo</title><style>
*{box-sizing:border-box}body{margin:0;background:#000;color:#fff;font-family:Arial,sans-serif}
main{height:100vh;height:100dvh;display:flex;align-items:center;justify-content:center;padding:5vw}
#lyrics{width:100%;text-align:center;font-size:clamp(32px,7vw,130px);font-weight:bold;line-height:1.2;white-space:pre-wrap;overflow-wrap:anywhere}
#controls{position:fixed;right:12px;bottom:12px;display:flex;gap:10px;align-items:center;color:#999;font-size:12px}
button{padding:8px;background:#222;color:#ccc;border:1px solid #444;border-radius:6px;cursor:pointer}
:fullscreen #controls{display:none}
</style></head><body><main><div id="lyrics" aria-live="polite"></div></main>
<div id="controls"><span id="status">Conectando…</span><button id="full">Tela cheia</button></div>
<script>
const lyrics=document.getElementById('lyrics'),status=document.getElementById('status');
let lastSuccess=0;
async function poll(){
 const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),3000);
 try{
  const response=await fetch('/state?t='+Date.now(),{cache:'no-store',signal:controller.signal});
  if(!response.ok)throw new Error('HTTP '+response.status);
  const data=await response.json();if(typeof data.text!=='string')throw new Error('Resposta inválida');
  if(lyrics.textContent!==data.text)lyrics.textContent=data.text;
  lastSuccess=Date.now();status.textContent='Conectado';
 }catch(error){status.textContent='Reconectando…';if(Date.now()-lastSuccess>5000)lyrics.textContent='';}
 finally{clearTimeout(timer);setTimeout(poll,200);}
}
document.getElementById('full').onclick=()=>{
 const element=document.documentElement;
 if(element.requestFullscreen)element.requestFullscreen().catch(()=>{});
 else if(element.webkitRequestFullscreen)element.webkitRequestFullscreen();
};
poll();
</script></body></html>'''

class LyricsServer(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, address, token='', ttl=10):
        super().__init__(address, Handler)
        self.token = token
        self.ttl = ttl
        self.state_lock = threading.Lock()
        self.text = ''
        self.updated_at = 0.0
        self.last_update = 0.0

class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(5)

    def log_message(self, fmt, *args):
        # Consultas de exibição não poluem o Terminal.
        pass

    def respond(self, code, content, content_type='application/json; charset=utf-8'):
        if isinstance(content, (dict, list)):
            content = json.dumps(content, ensure_ascii=False).encode('utf-8')
        elif isinstance(content, str):
            content = content.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(content)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        try:
            self.wfile.write(content)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        path = urlsplit(self.path).path
        if path in ('/', '/index.php'):
            self.respond(200, PAGE, 'text/html; charset=utf-8')
        elif path == '/state':
            with self.server.state_lock:
                expired = time.monotonic() - self.server.last_update > self.server.ttl
                state = {'text': '' if expired else self.server.text,
                         'updated_at': self.server.updated_at}
            self.respond(200, state)
        else:
            self.respond(404, {'error': 'Caminho não encontrado'})

    def do_POST(self):
        if urlsplit(self.path).path not in ('/post_lyrics', '/post_lyrics.php', '/music/post_lyrics.php'):
            self.respond(404, {'error': 'Caminho não encontrado'})
            return
        token = self.headers.get('X-Lyrics-Token', '')
        if self.server.token and not hmac.compare_digest(token.encode('utf-8'), self.server.token.encode('utf-8')):
            self.respond(403, {'error': 'Chave inválida'})
            return
        if self.headers.get('Transfer-Encoding'):
            self.respond(400, {'error': 'Use Content-Length'})
            return
        try:
            size = int(self.headers.get('Content-Length', '-1'))
        except ValueError:
            size = -1
        if size < 0:
            self.respond(411, {'error': 'Content-Length obrigatório'})
            return
        if size > 16384:
            self.respond(413, {'error': 'Conteúdo muito grande'})
            return
        try:
            data = json.loads(self.rfile.read(size).decode('utf-8'))
            if not isinstance(data, dict) or not isinstance(data.get('text'), str):
                raise ValueError('Envie JSON com text do tipo string')
            if len(data['text'].encode('utf-8')) > 8000:
                self.respond(413, {'error': 'Frase muito grande'})
                return
        except (ValueError, UnicodeError, OSError):
            self.respond(400, {'error': 'Envie JSON UTF-8 com text do tipo string'})
            return
        with self.server.state_lock:
            self.server.text = data['text']
            self.server.updated_at = time.time()
            self.server.last_update = time.monotonic()
        self.respond(200, {'ok': True})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='127.0.0.1', help='127.0.0.1 para uso local; 0.0.0.0 para rede local')
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--token', default='', help='Chave opcional; use a mesma TOKEN do lyrics_sender.py')
    parser.add_argument('--ttl', type=float, default=10, help='Limpar após N segundos sem POST (padrão: 10)')
    args = parser.parse_args()
    if args.ttl <= 0:
        parser.error('--ttl deve ser positivo')
    if args.host not in ('127.0.0.1', 'localhost', '::1') and not args.token:
        parser.error('Para atender pela rede, informe --token com a chave do lyrics_sender.py')
    try:
        server = LyricsServer((args.host, args.port), args.token, args.ttl)
    except OSError as error:
        parser.exit(1, 'Não foi possível iniciar o servidor: %s\n' % error)
    print('Servidor iniciado. Abra http://127.0.0.1:%s/ neste computador.' % server.server_port)
    if args.host == '0.0.0.0':
        print('Nas outras telas, use http://IP_DESTE_COMPUTADOR:%s/' % server.server_port)
    print('Mantenha este Terminal aberto. Ctrl+C encerra. A frase fica apenas na memória.')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nServidor encerrado.')
    finally:
        server.server_close()

if __name__ == '__main__':
    main()
