param(
    [Parameter(Mandatory=$false)]
    [string]$Prompt = "",

    [Parameter(Mandatory=$false)]
    [string]$Image,

    [Parameter(Mandatory=$false)]
    [double]$ReferenceStrength = 0.70,

    [Parameter(Mandatory=$false)]
    [int]$Steps = 35,

    [Parameter(Mandatory=$false)]
    [Nullable[int]]$Seed,

    [Parameter(Mandatory=$false)]
    [string]$Output = "skin.png",

    [Parameter(Mandatory=$false)]
    [string]$EndpointId = $env:RUNPOD_ENDPOINT_ID,

    [Parameter(Mandatory=$false)]
    [string]$ApiKey = $env:RUNPOD_API_KEY
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($EndpointId)) {
    throw "Missing Endpoint ID. Set RUNPOD_ENDPOINT_ID or pass -EndpointId."
}
if ([string]::IsNullOrWhiteSpace($ApiKey)) {
    throw "Missing API key. Set RUNPOD_API_KEY or pass -ApiKey."
}
if ([string]::IsNullOrWhiteSpace($Prompt) -and [string]::IsNullOrWhiteSpace($Image)) {
    throw "Provide -Prompt, -Image, or both."
}

$inputObject = [ordered]@{
    prompt = $Prompt
    steps = $Steps
    format = "modern"
}

if (-not [string]::IsNullOrWhiteSpace($Image)) {
    if (-not (Test-Path -LiteralPath $Image -PathType Leaf)) {
        throw "Image not found: $Image"
    }

    $fileInfo = Get-Item -LiteralPath $Image
    if ($fileInfo.Length -gt 6MB) {
        throw "Reference image must be 6 MB or smaller."
    }

    $imageBytes = [System.IO.File]::ReadAllBytes($fileInfo.FullName)
    $inputObject.reference_image_base64 = [Convert]::ToBase64String($imageBytes)
    $inputObject.reference_strength = $ReferenceStrength
}

if ($null -ne $Seed) {
    $inputObject.seed = $Seed.Value
}

$body = @{ input = $inputObject } | ConvertTo-Json -Depth 8 -Compress
$headers = @{ Authorization = "Bearer $ApiKey" }
$url = "https://api.runpod.ai/v2/$EndpointId/runsync?wait=300000"

Write-Host "Sending request to RunPod..."
$response = Invoke-RestMethod -Method Post -Uri $url -Headers $headers -ContentType "application/json" -Body $body -TimeoutSec 330

if ($response.status -ne "COMPLETED") {
    $response | ConvertTo-Json -Depth 10
    throw "RunPod job did not complete successfully. Status: $($response.status)"
}

if (-not $response.output.image_base64) {
    $response | ConvertTo-Json -Depth 10
    throw "RunPod response does not contain output.image_base64."
}

$pngBytes = [Convert]::FromBase64String($response.output.image_base64)
$outputPath = [System.IO.Path]::GetFullPath($Output)
[System.IO.File]::WriteAllBytes($outputPath, $pngBytes)

Write-Host "Saved: $outputPath"
Write-Host "Size: $($response.output.width)x$($response.output.height)"
Write-Host "Seed: $($response.output.seed)"
Write-Host "Mode: $($response.output.source_mode)"
