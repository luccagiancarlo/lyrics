#!/usr/bin/env bash
#
# teste_envio.sh - Testa o envio de uma letra ao post_lyrics.php
#
# Uso:
#   ./teste_envio.sh                      # envia uma letra de teste padrao
#   ./teste_envio.sh "Minha letra aqui"   # envia o texto informado
#
# Variaveis de ambiente opcionais:
#   LYRICS_URL    sobrescreve a URL do endpoint
#   LYRICS_TOKEN  sobrescreve o token de autenticacao
#
set -euo pipefail

URL="${LYRICS_URL:-https://luccasoftware.com.br/music/post_lyrics.php}"
TOKEN="${LYRICS_TOKEN:-3e8dd779f921ba3c7ee0e8490ebf85cfabc4b41e1e6c5f8e}"
# Se um argumento foi passado (mesmo vazio), usa ele; senao, letra padrao.
# Isso permite testar o envio de letra vazia com:  ./teste_envio.sh ""
if [ "$#" -ge 1 ]; then
  TEXT="$1"
else
  TEXT="Letra de teste - $(date '+%H:%M:%S')"
fi

# Monta o corpo JSON com o texto escapado corretamente (usa python3 se houver,
# senao faz um escape simples das aspas).
if command -v python3 >/dev/null 2>&1; then
  BODY=$(python3 -c 'import json,sys; print(json.dumps({"text": sys.argv[1]}, ensure_ascii=False))' "$TEXT")
else
  ESCAPED=${TEXT//\\/\\\\}
  ESCAPED=${ESCAPED//\"/\\\"}
  BODY="{\"text\":\"${ESCAPED}\"}"
fi

echo "==> URL:   $URL"
echo "==> Texto: $TEXT"
echo "==> Body:  $BODY"
echo "==> Enviando..."
echo

# -s silencioso, -S mostra erro, -w imprime o status HTTP ao final.
RESPONSE=$(curl -sS -X POST "$URL" \
  -H "Content-Type: application/json" \
  -H "X-Lyrics-Token: $TOKEN" \
  --data-binary "$BODY" \
  --max-time 10 \
  -w $'\n__HTTP_STATUS__:%{http_code}')

HTTP_STATUS=$(printf '%s' "$RESPONSE" | sed -n 's/.*__HTTP_STATUS__://p')
BODY_OUT=$(printf '%s' "$RESPONSE" | sed 's/__HTTP_STATUS__:[0-9]*$//')

echo "==> HTTP status: $HTTP_STATUS"
echo "==> Resposta:    $BODY_OUT"
echo

if [ "$HTTP_STATUS" = "200" ] && printf '%s' "$BODY_OUT" | grep -q '"ok"[[:space:]]*:[[:space:]]*true'; then
  echo "✔ Envio OK (ok=true)"
  exit 0
else
  echo "x Falha no envio (status != 200 ou sem ok=true)"
  exit 1
fi
