-- Edite para o caminho COMPLETO do Python 3 do seu computador.
-- macOS/Linux: execute "which python3" no Terminal.
-- Windows: execute "py -0p" e copie o caminho de python.exe.
local PYTHON = "/usr/local/Caskroom/miniconda/base/bin/python3"
local TRACK_NAME = "Lyrics"

local _, script_path, section, command = reaper.get_action_context()
local base = script_path:match("^(.*[/\\])")
local worker = base .. "lyrics_sender.py"
local folder = base .. "lyrics_runtime_" .. tostring(os.time()) .. "_" .. tostring(math.random(100000,999999))
reaper.RecursiveCreateDirectory(folder, 0)
local state_path = folder .. "/state.json"
local status_path = folder .. "/status.txt"
local function quote(s) return '"' .. s .. '"' end
local function json_string(s)
 return '"' .. s:gsub('[%z\1-\31\\"]', function(c)
  if c == '"' then return '\\"' end
  if c == '\\' then return '\\\\' end
  return string.format('\\u%04x', c:byte())
 end) .. '"'
end
local function write(text, stop)
 local tmp = state_path .. '.tmp'
 local f = io.open(tmp,'wb')
 if not f then return false end
 f:write('{"text":' .. json_string(text) .. ',"heartbeat":' .. os.time() .. ',"stop":' .. tostring(stop) .. '}')
 f:close()
 -- Windows não substitui arquivos existentes via rename. Uma leitura no intervalo será repetida pelo worker.
 os.remove(state_path)
 return os.rename(tmp,state_path)
end
if not reaper.file_exists(PYTHON) or not reaper.file_exists(worker) then
 reaper.ShowMessageBox('Confira o caminho PYTHON e coloque lyrics_sender.py ao lado deste Lua.', 'Lyrics',0)
 return
end
write('',false)
reaper.ExecProcess(quote(PYTHON) .. ' ' .. quote(worker) .. ' ' .. quote(folder), -1)
reaper.SetToggleCommandState(section,command,1)
reaper.RefreshToolbar2(section,command)
reaper.atexit(function()
 write('',true)
 reaper.SetToggleCommandState(section,command,0)
 reaper.RefreshToolbar2(section,command)
end)
local started = reaper.time_precise()
local last_text, last_write, last_status = nil, 0, 0
local function current_text()
 local play = reaper.GetPlayState()
 if (play & 1) == 0 then return '' end -- pausa e stop limpam
 local pos = reaper.GetPlayPosition()
 local track
 for i=0,reaper.CountTracks(0)-1 do
  local tr = reaper.GetTrack(0,i)
  local _, name = reaper.GetTrackName(tr)
  if name:lower() == TRACK_NAME:lower() then track=tr;break end
 end
 if not track then return '' end
 local selected, start = nil, -math.huge
 for i=0,reaper.CountTrackMediaItems(track)-1 do
  local item = reaper.GetTrackMediaItem(track,i)
  local at = reaper.GetMediaItemInfo_Value(item,'D_POSITION')
  local len = reaper.GetMediaItemInfo_Value(item,'D_LENGTH')
  if pos >= at and pos < at+len and at >= start then selected=item;start=at end
 end
 if not selected then return '' end
 local _, notes = reaper.GetSetMediaItemInfo_String(selected,'P_NOTES','',false)
 return notes
end
local function loop()
 local now = reaper.time_precise()
 local text = current_text()
 if text ~= last_text or now-last_write >= 1 then
  if write(text,false) then last_text=text;last_write=now end
 end
 if now-last_status > 3 then
  local f=io.open(status_path,'rb')
  if f then
   local status=f:read('*a');f:close()
   if status~='OK' then reaper.ShowConsoleMsg('Lyrics: '..status..'\n') end
  elseif now-started > 3 then
   reaper.ShowConsoleMsg('Lyrics: worker sem resposta; confira o Python.\n')
  end
  last_status=now
 end
 reaper.defer(loop)
end
loop()
