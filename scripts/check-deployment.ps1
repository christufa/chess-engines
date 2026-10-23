<#
.SYNOPSIS
  Check the deployed chess-engines API end to end: analyse the starting position from a
  pod in the cluster, then through Cloudflare Access with a service token, and show that
  a request without a token is refused.

.DESCRIPTION
  Needs kubectl access to the openings cluster (az aks get-credentials, your IP in its
  authorized ranges) and read access to the openings Key Vault (your IP in its firewall).
  The token is read from Key Vault into this process only and never printed.

.EXAMPLE
  ./scripts/check-deployment.ps1 -KeyVault <vault name>
#>
param(
  [Parameter(Mandatory)] [string] $KeyVault,
  [string] $Token = 'shared',
  [string] $Hostname = 'chess-engines.generops.dev'
)
$ErrorActionPreference = 'Stop'
$start = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'
$body = @{ fen = $start; depth = 18; multipv = 3 } | ConvertTo-Json -Compress

function Show($result) {
  "{0} ({1} ms)" -f $result.engine.id, $result.time_ms
  $result.lines | ForEach-Object {
    $score = if ($null -ne $_.score.mate) { "mate $($_.score.mate)" } else { "$($_.score.cp) cp" }
    "  {0}. {1,-5} {2,8}  depth {3}  {4}" -f $_.rank, $_.san, $score, $_.depth, (($_.pv_san | Select-Object -First 6) -join ' ')
  }
}

Write-Host "`n== Inside the cluster (a pod in openings-research) ==" -ForegroundColor Cyan
kubectl -n chess-engines get deploy,scaledobject,pods -o wide
$overrides = @{ spec = @{ securityContext = @{ runAsNonRoot = $true; runAsUser = 65532; seccompProfile = @{ type = 'RuntimeDefault' } }
  containers = @(@{ name = 'check'; image = 'curlimages/curl:8.17.0'; command = @('curl', '-fsS', '-X', 'POST',
    'http://chess-engines.chess-engines.svc.cluster.local/v1/analyse', '-H', 'content-type: application/json', '-d', $body)
    securityContext = @{ allowPrivilegeEscalation = $false; capabilities = @{ drop = @('ALL') } } }) } } | ConvertTo-Json -Depth 10 -Compress
# openings-research admits only its own images, so the probe pod runs in the argo namespace.
$inside = kubectl -n argo run "chess-engines-check-$([guid]::NewGuid().ToString('N').Substring(0, 6))" --rm -i --restart=Never `
  --image=curlimages/curl:8.17.0 --overrides=$overrides --quiet
Show ($inside | ConvertFrom-Json)

Write-Host "`n== Through Cloudflare Access with service token '$Token' ==" -ForegroundColor Cyan
$headers = @{
  'CF-Access-Client-Id'     = az keyvault secret show --vault-name $KeyVault -n "chess-engines-$Token-client-id" --query value -o tsv
  'CF-Access-Client-Secret' = az keyvault secret show --vault-name $KeyVault -n "chess-engines-$Token-client-secret" --query value -o tsv
}
Show (Invoke-RestMethod -Method Post -Uri "https://$Hostname/v1/analyse" -Headers $headers -ContentType 'application/json' -Body $body)

Write-Host "`n== Without a token ==" -ForegroundColor Cyan
$status = try { (Invoke-WebRequest -Method Post -Uri "https://$Hostname/v1/analyse" -ContentType 'application/json' -Body $body -MaximumRedirection 0).StatusCode } catch { [int]$_.Exception.Response.StatusCode }
"HTTP $status (expected 401 or 403)"
if ($status -notin 401, 403) { throw "the hostname answered without a service token" }
