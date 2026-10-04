<?php
if (isset($_GET['state'])) {
    require __DIR__ . '/config.php';
    header('Content-Type: application/json; charset=utf-8');
    header('Cache-Control: no-store, no-cache, must-revalidate');
    $raw = '';
    if (is_file(LYRICS_FILE)) {
        $fp = fopen(LYRICS_FILE, 'rb');
        if ($fp && flock($fp, LOCK_SH)) {
            $raw = stream_get_contents($fp);
            flock($fp, LOCK_UN);
        }
        if ($fp) fclose($fp);
    }
    $state = json_decode($raw, true);
    if (is_array($state) && microtime(true) - ($state['updated_at'] ?? 0) > 10) $state['text'] = '';
    echo json_encode(is_array($state) ? $state : ['text'=>'', 'updated_at'=>0], JSON_UNESCAPED_UNICODE);
    exit;
}
header('Cache-Control: no-store');
?>
<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Letra ao vivo</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#000;color:#fff;font-family:Arial,sans-serif}
main{height:100vh;height:100dvh;display:flex;align-items:center;justify-content:center;padding:5vw}
#lyrics{width:100%;text-align:center;font-size:8vw;font-size:clamp(32px,7vw,130px);line-height:1.2;font-weight:700;white-space:pre-wrap;overflow-wrap:anywhere}
#controls{position:fixed;right:12px;bottom:12px;display:flex;gap:10px;align-items:center;font-size:12px;color:#999}
button{background:#222;color:#ccc;border:1px solid #444;border-radius:6px;padding:8px;cursor:pointer}
:fullscreen #controls{display:none}
</style></head><body><main><div id="lyrics" aria-live="polite"></div></main>
<div id="controls"><span id="status">Conectando…</span><button id="full">Tela cheia</button></div>
<script>
// Polyfill p/ Chromium antigo (Pi/Buster = Chromium 78): AbortSignal.timeout so existe no Chrome 103+.
if(!('timeout' in AbortSignal)){AbortSignal.timeout=function(ms){var c=new AbortController();setTimeout(function(){c.abort();},ms);return c.signal;};}
const lyrics=document.getElementById('lyrics'), status=document.getElementById('status');
let lastSuccess=0;
async function poll(){
 try{
  const response=await fetch('index.php?state=1&t='+Date.now(),{cache:'no-store',signal:AbortSignal.timeout(3000)});
  if(!response.ok)throw new Error('HTTP '+response.status);
  const data=await response.json();
  if(typeof data.text!=='string')throw new Error('Resposta inválida');
  if(lyrics.textContent!==data.text)lyrics.textContent=data.text;
  lastSuccess=Date.now();status.textContent='Conectado';
 }catch(e){status.textContent='Reconectando…';if(Date.now()-lastSuccess>5000)lyrics.textContent='';}
 setTimeout(poll,200);
}
document.getElementById('full').onclick=()=>document.documentElement.requestFullscreen().catch(()=>{});
poll();
</script></body></html>
