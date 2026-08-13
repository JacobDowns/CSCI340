param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = 'Stop'
$failures = [System.Collections.Generic.List[string]]::new()
$qmdFiles = Get-ChildItem -LiteralPath $ProjectRoot -Recurse -Filter '*.qmd' -File

foreach ($file in $qmdFiles) {
    $text = Get-Content -LiteralPath $file.FullName -Raw
    $lines = Get-Content -LiteralPath $file.FullName

    if ($lines.Count -lt 3 -or $lines[0].Trim() -ne '---') {
        $failures.Add("Missing YAML front matter: $($file.FullName)")
    } else {
        $closing = ($lines | Select-Object -Skip 1 | Select-String -SimpleMatch '---' | Select-Object -First 1)
        if (-not $closing) {
            $failures.Add("Unclosed YAML front matter: $($file.FullName)")
        }
    }

    $fenceCount = ([regex]::Matches($text, '(?m)^```')).Count
    if ($fenceCount % 2 -ne 0) {
        $failures.Add("Unbalanced code fences: $($file.FullName)")
    }

    foreach ($match in [regex]::Matches($text, '\[[^\]]+\]\(([^)#?]+\.qmd)\)')) {
        $relativeTarget = $match.Groups[1].Value
        $target = Join-Path $file.DirectoryName $relativeTarget
        if (-not (Test-Path -LiteralPath $target -PathType Leaf)) {
            $failures.Add("Broken QMD link in $($file.FullName): $relativeTarget")
        }
    }
}

$config = Get-Content -LiteralPath (Join-Path $ProjectRoot '_quarto.yml') -Raw
foreach ($match in [regex]::Matches($config, '(?m)^\s*href:\s*["'']?([^"''\r\n]+\.qmd)["'']?\s*$')) {
    $target = Join-Path $ProjectRoot $match.Groups[1].Value
    if (-not (Test-Path -LiteralPath $target -PathType Leaf)) {
        $failures.Add("Broken navigation target: $($match.Groups[1].Value)")
    }
}

if ($config -match 'https://example\.edu') {
    Write-Warning 'The site-url is still a publication placeholder.'
}

if ($failures.Count -gt 0) {
    $failures | ForEach-Object { Write-Error $_ }
    exit 1
}

Write-Output "Static validation passed for $($qmdFiles.Count) Quarto source files."
