# Letras do Cubase 10 no Mac

O receptor recebe notas MIDI e envia o JSON {"text":"frase"} ao endpoint existente. Não lê nomes de partes, notas de texto ou marcadores do Cubase. Substitui o Lua e o lyrics_sender.py na operação com Cubase; não altere os PHP ou o servidor local. Execute apenas um remetente por apresentação.

## 1. Instalar

Descompacte e abra o Terminal dentro da pasta cubase_lyrics. Use Python 3.8 ou superior (prefira seu Python 3.10 ou 3.12 já instalado, se compatível com seu Mac).

```bash
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Nas próximas vezes basta abrir essa pasta, executar source .venv/bin/activate e iniciar o receptor. Se houver erro de compilação ao instalar python-rtmidi, envie o erro junto com python3 --version e sw_vers: a disponibilidade de um pacote binário depende da versão do Python e do macOS.

## 2. Configuração do destino

Edite config_midi.json com um editor de texto simples. Para o PHP já hospedado, mantenha url e preencha token com a mesma chave do config.php ou TOKEN do lyrics_sender.py. Não use o texto literal SUA_CHAVE. Não compartilhe sua chave.

Para servidor_lyrics.py na mesma máquina:

```json
{
  "url": "http://127.0.0.1:8080/post_lyrics",
  "token": "",
  "midi_port": "Lyrics",
    "http_timeout": 2,
  "max_note_seconds": 300
}
```

Inicie o servidor local em outro Terminal. Se ele foi iniciado com --token, coloque essa mesma chave no JSON. Para um servidor local em outra máquina, substitua 127.0.0.1 pelo IP daquela máquina.

HTTPS usa os certificados de certifi, mantendo validação de certificado. Se ocorrer um erro SSL, atualize certifi com python -m pip install --upgrade certifi; se persistir, verifique a cadeia do servidor ou o certificado da rede. O programa não desabilita a validação SSL.

## 3. Testar o POST antes do MIDI

Abra a página que já exibe sua letra e execute:

```bash
python receptor_midi.py --teste-nota 60 --duracao 4
```

A frase aparece por quatro segundos e o receptor envia a limpeza. Esse teste não abre a porta MIDI. 403 significa chave errada; 404 significa caminho incorreto. Edite frases.json se quiser outra frase.

## 4. Criar conexão MIDI no Mac

1. Aplicativos → Utilitários → Configuração de Áudio e MIDI.
2. Janela → Mostrar Estúdio MIDI.
3. Abra IAC Driver e marque Dispositivo online.
4. Crie/renomeie uma porta como Lyrics e clique Aplicar.

O IAC é uma conexão MIDI entre aplicativos, sem instrumento físico.

Liste as portas vistas pelo Python:

```bash
python receptor_midi.py --listar-portas
```

Use o nome exato retornado em midi_port, ou passe na execução:

```bash
python receptor_midi.py --porta "IAC Driver Lyrics" --monitor
```

O nome acima é exemplo; copie o nome listado na sua máquina. Se houver somente uma porta contendo Lyrics, a configuração padrão consegue encontrá-la pelo trecho do nome.

## 5. Track MIDI no Cubase

1. Crie uma track MIDI chamada Lyrics. O nome é organizacional; o Python recebe a porta MIDI, não o nome da track.
2. No Inspector, selecione a saída IAC correspondente à porta Lyrics.
3. Para uma track por canal, selecione o canal correspondente (1 a 16). Não encaminhe essa track a um VST de instrumento.
4. Deixe a entrada da track como Not Connected e o monitor desativado, para evitar realimentação do IAC para a própria saída.
5. Insira uma parte MIDI e desenhe as notas nos momentos da letra.
6. Evite notas sobrepostas. O início de cada nota mostra a frase e o fim limpa.

No canal 1, o número MIDI 60 é a primeira frase, 61 a segunda e 62 a terceira. A nota 60 dos canais 2 e 3 tem outras frases. A numeração de oitavas exibida pelo Cubase varia conforme configuração; não dependa de um rótulo como C3 ou C4. Com --monitor, o Terminal informa note=60, note=61 etc. para conferir.

Você também pode importar demo_lyrics.mid em uma track MIDI (ou arrastar para o projeto) e atribuir a saída IAC à track importada. A demonstração contém cinco frases de quatro segundos com intervalos de um segundo, canais 1, 2 e 3 e andamento de 120 BPM. O tempo real no projeto depende do andamento e de como o Cubase importar o tempo. Não substitua o andamento do seu VS sem intenção; este é um teste de disparos.

## 6. Cadastrar suas frases

Edite frases.json. As chaves combinam canal (1 a 16) e número MIDI (0 a 127), com até 2.048 associações:

```json
{
  "1:60": "Primeira frase",
  "1:61": "Segunda frase",
  "2:60": "Linha um\nLinha dois",
  "1:0": ""
}
```

A nota 0 do canal 1 funciona como comando explícito de limpar porque foi associada a texto vazio. Qualquer nota pode repetir uma frase em vários pontos da música. Para mais frases, use outros números disponíveis (no máximo 2.048 associações por arquivo). Encerre e reinicie o receptor após editar as frases ou a configuração. Para trocar de repertório use --frases outro_arquivo.json.

Não sobreponha notas com o mesmo número no mesmo canal. Se combinações diferentes de canal e nota se sobrepuserem, a última iniciada tem prioridade; o note_off da anterior não apaga a nova. O término da atual limpa, sem restaurar a anterior. Notas sem associação são informadas e ignoradas.

## 7. Iniciar a apresentação

```bash
python receptor_midi.py --monitor
```

Mantenha esse Terminal aberto, abra sua tela de exibição e dê Play no Cubase. O modo --monitor mostra mensagens para diagnosticar; pode omiti-lo depois. Ctrl+C encerra e tenta limpar a tela.

O receptor mantém a frase no servidor com atualização a cada três segundos. Os POSTs são sequenciais, em thread separada, e falhas são repetidas com o estado mais recente. Se eventos forem extremamente curtos, estados intermediários podem ser substituídos antes de chegar à rede. Faça as notas durarem o tempo de leitura da frase e teste a conexão no local.

## Stop, pausa e saltos: diferenças em relação ao REAPER

O receptor MIDI não lê a posição nem o transporte diretamente do Cubase. Ele limpa com note_off da nota ativa, note_on de velocidade zero, All Notes Off (CC123), All Sound Off (CC120), Stop MIDI, Reset MIDI, ou ao encerrar com Ctrl+C. Stop MIDI só funciona se o Cubase realmente transmitir a mensagem pela porta; não se presume que isso esteja ativado.

Teste o Stop enquanto uma nota está ativa. Se o Cubase não enviar note_off/CC/Stop, a frase permanecerá; a atualização periódica mantém essa frase viva no endpoint. Existe um limite de segurança max_note_seconds (padrão 300 segundos), que limpa após esse tempo sem nova nota. Não é uma detecção automática de Stop. Pode alterar o limite ou usar 0 para desativá-lo.

Ao iniciar no meio de uma nota, a frase só aparecerá se o Cubase transmitir o note_on correspondente (por exemplo, dependendo de sua configuração de chase). Teste saltos e ciclos. O caminho previsível é iniciar antes do começo da nota; podemos adicionar sincronização por posição posteriormente se isso for necessário.

## Validação e referências

Foram verificados os eventos com mensagens MIDI simuladas, note_on/off, velocidade zero, prioridade em sobreposição, canal, CC123, limite de duração, JSON e POST contra um servidor HTTP de teste local. Não foi possível testar o CoreMIDI/IAC ou o Cubase real neste ambiente.

- IAC Apple: https://support.apple.com/guide/audio-midi-setup/ams1013/mac
- Mido: https://mido.readthedocs.io/en/latest/ports/

## Versão com 16 canais

O receptor agora escuta todos os 16 canais. A configuração antiga channel não filtra mais eventos. Arquivos antigos com chaves "60", "61" continuam aceitos e são interpretados como "1:60", "1:61". Não use simultaneamente "60" e "1:60": seriam duplicados.

Organização recomendada: tracks Lyrics 1, Lyrics 2 etc., saída IAC Lyrics em todas, cada track configurada com seu canal. Cada canal tem 128 notas. O exemplo reserva apenas 1:0 para limpar, restando 2.047 combinações para frases; pode usar 1:0 para texto também e aproveitar todas as 2.048.

Para a demo com canais misturados em uma única track, configure o canal da track como Any/Qualquer, para preservar os canais gravados no arquivo MIDI. Se forçar canal 1, todos os disparos de nota 60 usarão 1:60. Alternativamente, separe os eventos em tracks e atribua os canais respectivos.

Teste direto do canal 2:

```bash
python receptor_midi.py --teste-canal 2 --teste-nota 60
```

Mido mostra os canais internamente de 0 a 15 no monitor bruto (channel=0 significa canal 1). As chaves de frases.json e a mensagem “Canal/nota” usam 1 a 16, como o Cubase.

A prioridade é global: há uma só frase na tela, mesmo que várias tracks enviem. Note_off de outra combinação não apaga a frase atual. CC120/CC123 limpam apenas se forem do canal da frase atual; Stop/Reset MIDI recebidos limpam todos.
