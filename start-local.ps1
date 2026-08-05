# Sobe tudo que roda localmente: Docker Desktop autoinicia sozinho no
# login (Postgres/Redis/Evolution API tem restart:always), esse script
# so cuida do agente-ia-core, que roda via venv fora do Docker.
Set-Location $PSScriptRoot

# Espera o Docker Desktop terminar de subir os containers (evita a
# uvicorn tentar falar com a Evolution API antes dela estar pronta).
$maxWait = 60
$waited = 0
while ($waited -lt $maxWait) {
    $running = docker ps --filter "name=agente-ia-core-evolution-api-1" --filter "status=running" -q
    if ($running) { break }
    Start-Sleep -Seconds 2
    $waited += 2
}

& ".\venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8000
