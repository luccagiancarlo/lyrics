<?php
require __DIR__ . '/config.php';
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');
function reply($code, $body) { http_response_code($code); echo json_encode($body); exit; }
if ($_SERVER['REQUEST_METHOD'] !== 'POST') reply(405, ['error'=>'Use POST']);
if (!hash_equals(LYRICS_TOKEN, $_SERVER['HTTP_X_LYRICS_TOKEN'] ?? '')) reply(403, ['error'=>'Chave inválida']);
$raw = file_get_contents('php://input', false, null, 0, 16385);
if (strlen($raw) > 16384) reply(413, ['error'=>'Conteúdo muito grande']);
$data = json_decode($raw, true);
if (!is_array($data) || !isset($data['text']) || !is_string($data['text'])) reply(400, ['error'=>'Envie JSON com text']);
if (strlen($data['text']) > 8000) reply(413, ['error'=>'Frase muito grande']);
$state = json_encode(['text'=>$data['text'], 'updated_at'=>microtime(true)], JSON_UNESCAPED_UNICODE);
// LOCK_EX + leitura com LOCK_SH evitam que a tela leia uma escrita incompleta.
if ($state === false || file_put_contents(LYRICS_FILE, $state, LOCK_EX) === false) reply(500, ['error'=>'Falha ao salvar. Verifique permissões.']);
reply(200, ['ok'=>true]);
