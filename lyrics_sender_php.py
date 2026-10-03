#!/usr/bin/env python3
"""Worker iniciado pelo Lua. Python 3.8+; sem pacotes externos."""
import json, sys, time, urllib.request
from pathlib import Path
URL = 'https://luccasoftware.com.br/music/post_lyrics.php'
TOKEN = '3e8dd779f921ba3c7ee0e8490ebf85cfabc4b41e1e6c5f8e'

def run(folder):
    folder = Path(folder)
    last = None
    last_sent = 0.0
    while True:
        try:
            state = json.loads((folder / 'state.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            time.sleep(.05)
            continue
        # O heartbeat é atualizado pelo REAPER. Encerrar se o aplicativo fechar.
        if time.time() - state['heartbeat'] > 10:
            state = dict(state, text='', stop=True)
        text = state['text']
        if text != last or time.monotonic() - last_sent >= 3:
            try:
                request = urllib.request.Request(URL, data=json.dumps({'text':text}, ensure_ascii=False).encode('utf-8'),
                    headers={'Content-Type':'application/json', 'X-Lyrics-Token':TOKEN}, method='POST')
                with urllib.request.urlopen(request, timeout=2) as response:
                    result = json.loads(response.read())
                    if result.get('ok') is not True:
                        raise ValueError('Resposta sem ok=true')
                last = text
                last_sent = time.monotonic()
                (folder / 'status.txt').write_text('OK', encoding='utf-8')
            except Exception as error:
                (folder / 'status.txt').write_text(str(error), encoding='utf-8')
                if state.get('stop'):
                    break
                time.sleep(.3)
                continue
        if state.get('stop'):
            break
        time.sleep(.05)

if __name__ == '__main__':
    run(sys.argv[1])
