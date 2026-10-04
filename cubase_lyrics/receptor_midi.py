#!/usr/bin/env python3
"""Cubase → MIDI IAC → frases → POST. Python 3.8+. Use --help."""
import argparse
import json
import ssl
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

BASE = Path(__file__).resolve().parent

class PhraseState:
    """A última nota ativada tem prioridade; seu note_off limpa sem reexibir anteriores."""
    def __init__(self, phrases, channel=1, max_note_seconds=300):
        self.phrases = phrases
        self.channel = channel - 1
        self.max_note_seconds = max_note_seconds
        self.lock = threading.Lock()
        self.text = ''
        self.active = None
        self.active_since = 0
        self.revision = 0

    def clear(self):
        with self.lock:
            self.active = None
            self.text = ''
            self.revision += 1

    def snapshot(self):
        with self.lock:
            if self.active is not None and self.max_note_seconds and time.monotonic() - self.active_since > self.max_note_seconds:
                self.active = None
                self.text = ''
                self.revision += 1
                print('Limpeza: duração máxima da nota excedida.', flush=True)
            return self.revision, self.text

    def handle(self, msg):
        if msg.type in ('stop', 'reset'):
            self.clear()
            return
        if getattr(msg, 'channel', None) != self.channel:
            return
        if msg.type == 'control_change' and msg.control in (120, 123):
            self.clear()
            return
        if msg.type not in ('note_on', 'note_off'):
            return
        if msg.type == 'note_on' and msg.velocity > 0:
            text = self.phrases.get(str(msg.note))
            if text is None:
                print('Nota %s sem frase cadastrada; ignorada.' % msg.note, flush=True)
                return
            with self.lock:
                self.active = msg.note
                self.active_since = time.monotonic()
                self.text = text
                self.revision += 1
            print('Nota %s → %s' % (msg.note, text or '[limpar]'), flush=True)
        else:
            with self.lock:
                if self.active != msg.note:
                    return
                self.active = None
                self.text = ''
                self.revision += 1
            print('Nota %s terminou → limpar' % msg.note, flush=True)

class Sender:
    def __init__(self, config):
        self.url = config['url']
        self.token = config.get('token', '')
        self.timeout = config.get('http_timeout', 2)
        self.context = None
        if urlsplit(self.url).scheme == 'https':
            import certifi
            self.context = ssl.create_default_context(cafile=certifi.where())

    def send(self, text):
        payload = json.dumps({'text': text}, ensure_ascii=False).encode('utf-8')
        headers = {'Content-Type': 'application/json'}
        if self.token:
            headers['X-Lyrics-Token'] = self.token
        request = urllib.request.Request(self.url, data=payload, headers=headers, method='POST')
        with urllib.request.urlopen(request, timeout=self.timeout, context=self.context) as response:
            result = json.loads(response.read(16384))
            if not isinstance(result, dict) or result.get('ok') is not True:
                raise ValueError('O endpoint não retornou ok=true')

    def run(self, state, closing):
        sent_revision = -1
        last_sent = 0
        last_error = ''
        while not closing.is_set():
            revision, text = state.snapshot()
            if revision != sent_revision or time.monotonic() - last_sent >= 3:
                try:
                    self.send(text)
                    sent_revision = revision
                    last_sent = time.monotonic()
                    if last_error:
                        print('Envio restabelecido.', flush=True)
                    last_error = ''
                except Exception as error:
                    detail = str(error)
                    if detail != last_error:
                        print('Falha no POST: %s. Vou repetir com o estado mais recente.' % detail, flush=True)
                    last_error = detail
                    closing.wait(.4)
                    continue
            closing.wait(.02)
        # Mesmo processo e sequência: nenhum POST anterior concorre com a limpeza final.
        try:
            self.send('')
            print('Tela limpa; receptor encerrado.', flush=True)
        except Exception as error:
            print('Não foi possível limpar ao encerrar: %s' % error, flush=True)


def read_config(path):
    config = json.loads(path.read_text(encoding='utf-8'))
    url = urlsplit(config.get('url', ''))
    if url.scheme not in ('http', 'https') or not url.netloc:
        raise ValueError('Configure uma URL http ou https válida')
    if not isinstance(config.get('token', ''), str):
        raise ValueError('token precisa ser um texto')
    channel = config.get('channel', 1)
    if not isinstance(channel, int) or isinstance(channel, bool) or not 1 <= channel <= 16:
        raise ValueError('channel deve ser de 1 a 16')
    for name, default in [('http_timeout', 2), ('max_note_seconds', 300)]:
        value = config.get(name, default)
        if not isinstance(value, (int, float)) or value < 0 or (name == 'http_timeout' and value == 0):
            raise ValueError('%s inválido' % name)
    return config


def read_phrases(path):
    phrases = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(phrases, dict):
        raise ValueError('frases.json deve conter um objeto com números MIDI e textos')
    for key, text in phrases.items():
        if not key.isdigit() or str(int(key)) != key or not 0 <= int(key) <= 127:
            raise ValueError('Número MIDI inválido: %s' % key)
        if not isinstance(text, str) or len(text.encode('utf-8')) > 8000:
            raise ValueError('Frase inválida ou longa demais na nota %s' % key)
    return phrases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=BASE / 'config_midi.json')
    parser.add_argument('--frases', type=Path, default=BASE / 'frases.json')
    parser.add_argument('--listar-portas', action='store_true')
    parser.add_argument('--porta', help='Nome exato da porta MIDI; substitui o arquivo de configuração')
    parser.add_argument('--monitor', action='store_true', help='Exibir todas as mensagens MIDI recebidas')
    parser.add_argument('--teste-nota', type=int, help='Enviar a frase desta nota sem abrir MIDI')
    parser.add_argument('--duracao', type=float, default=4, help='Duração do teste em segundos')
    args = parser.parse_args()
    try:
        if args.listar_portas:
            import mido
            mido.set_backend('mido.backends.rtmidi')
            names = mido.get_input_names()
            print('\n'.join(names) if names else 'Nenhuma porta. Ative o IAC Driver e crie Lyrics.')
            return
        config = read_config(args.config)
        phrases = read_phrases(args.frases)
        sender = Sender(config)
        if urlsplit(config['url']).scheme == 'https' and not config.get('token'):
            raise ValueError('Preencha token com a chave do config.php ou do lyrics_sender.py')
        state = PhraseState(phrases, config.get('channel', 1), config.get('max_note_seconds', 300))
        closing = threading.Event()
        if args.teste_nota is not None:
            text = phrases.get(str(args.teste_nota))
            if text is None or args.duracao <= 0:
                raise ValueError('Escolha uma nota cadastrada e duração positiva')
            try:
                sender.send(text)
                print('Frase enviada. Limpando em %s segundos…' % args.duracao, flush=True)
                time.sleep(args.duracao)
            finally:
                sender.send('')
            return
        import mido
        mido.set_backend('mido.backends.rtmidi')
        names = mido.get_input_names()
        name = args.porta or config.get('midi_port', '')
        if name not in names:
            candidates = [n for n in names if name and name.lower() in n.lower()]
            if len(candidates) != 1:
                raise ValueError('Porta não encontrada ou ambígua. Use --listar-portas e --porta com o nome exato.')
            name = candidates[0]
        with mido.open_input(name) as port:
            print('Ouvindo %s, canal %s. Ctrl+C encerra.' % (name, state.channel + 1), flush=True)
            worker = threading.Thread(target=sender.run, args=(state, closing), daemon=True)
            worker.start()
            try:
                while True:
                    for msg in port.iter_pending():
                        if args.monitor:
                            print('MIDI:', msg, flush=True)
                        state.handle(msg)
                    time.sleep(.005)
            except KeyboardInterrupt:
                pass
            finally:
                closing.set()
                worker.join(config.get('http_timeout', 2) * 2 + 2)
    except KeyboardInterrupt:
        pass
    except (OSError, ValueError, ImportError, RuntimeError) as error:
        parser.exit(1, 'Erro: %s\n' % error)

if __name__ == '__main__':
    main()
