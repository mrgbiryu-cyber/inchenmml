param(
    [string]$OutputDir = "deploy/backups"
)

$ErrorActionPreference = "Stop"
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$targetDir = Join-Path $OutputDir $timestamp

New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
Write-Host "[INFO] backup target: $targetDir"

# PostgreSQL backup
if ($env:PGHOST -and $env:PGUSER -and $env:PGDATABASE) {
    $pgDumpPath = Join-Path $targetDir "postgres.sql"
    Write-Host "[INFO] running pg_dump..."
    & pg_dump -h $env:PGHOST -p ${env:PGPORT} -U $env:PGUSER $env:PGDATABASE | Out-File -FilePath $pgDumpPath -Encoding utf8
} else {
    Write-Host "[WARN] PGHOST/PGUSER/PGDATABASE not set. skipping postgres backup."
}

# Redis snapshot trigger
if ($env:REDIS_URL) {
    Write-Host "[INFO] triggering redis BGSAVE..."
    & redis-cli -u $env:REDIS_URL BGSAVE | Out-Null
} else {
    Write-Host "[WARN] REDIS_URL not set. skipping redis backup trigger."
}

# Neo4j cypher export (requires APOC and cypher-shell)
if ($env:NEO4J_URI -and $env:NEO4J_USER -and $env:NEO4J_PASSWORD) {
    $neo4jDumpPath = Join-Path $targetDir "neo4j_export.cypher"
    $query = "CALL apoc.export.cypher.all('$neo4jDumpPath', {format:'cypher-shell'})"
    Write-Host "[INFO] exporting neo4j cypher..."
    & cypher-shell -a $env:NEO4J_URI -u $env:NEO4J_USER -p $env:NEO4J_PASSWORD $query | Out-Null
} else {
    Write-Host "[WARN] NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD not set. skipping neo4j export."
}

Write-Host "[INFO] backup script completed"
