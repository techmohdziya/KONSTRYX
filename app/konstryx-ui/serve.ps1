# KONSTRYX — PowerShell fallback server (used when Python is not installed).
# Serves ./webapp at / and the SAPUI5 runtime at /resources.

param(
	[int]$Port = 8080,
	[string]$Runtime = "C:\Users\Ziya\Documents\Claude\sapui5-rt-1.150.0"
)

$ErrorActionPreference = "Stop"
$here   = Split-Path -Parent $MyInvocation.MyCommand.Path
$webapp = Join-Path $here "webapp"
$res    = Join-Path $Runtime "resources"

if (-not (Test-Path $res)) {
	Write-Host ""
	Write-Host "  Cannot find the SAPUI5 runtime." -ForegroundColor Red
	Write-Host "  Looked for: $res"
	Write-Host "  Run with:   powershell -ExecutionPolicy Bypass -File serve.ps1 -Runtime 'D:\path\to\sapui5-rt-1.150.0'"
	Write-Host ""
	exit 1
}

$mime = @{
	".html"="text/html; charset=utf-8"; ".js"="application/javascript; charset=utf-8";
	".json"="application/json; charset=utf-8"; ".xml"="application/xml; charset=utf-8";
	".css"="text/css; charset=utf-8"; ".properties"="text/plain; charset=utf-8";
	".png"="image/png"; ".jpg"="image/jpeg"; ".gif"="image/gif"; ".svg"="image/svg+xml";
	".ico"="image/x-icon"; ".woff"="font/woff"; ".woff2"="font/woff2"; ".ttf"="font/ttf";
	".map"="application/json; charset=utf-8"
}

$listener = New-Object System.Net.HttpListener
$listener.Prefixes.Add("http://localhost:$Port/")
try {
	$listener.Start()
} catch {
	Write-Host ""
	Write-Host "  Could not open port $Port. Try another one:  serve.ps1 -Port 8090" -ForegroundColor Red
	Write-Host ""
	exit 1
}

Write-Host ""
Write-Host "  KONSTRYX is running at  http://localhost:$Port/index.html" -ForegroundColor Green
Write-Host "  UI5 runtime            $Runtime"
Write-Host "  Press Ctrl+C to stop."
Write-Host ""
Start-Process "http://localhost:$Port/index.html" | Out-Null

while ($listener.IsListening) {
	try {
		$ctx = $listener.GetContext()
	} catch { break }

	$rel = [System.Uri]::UnescapeDataString($ctx.Request.Url.AbsolutePath)
	if ($rel -eq "/" ) { $rel = "/index.html" }

	if ($rel -like "/resources/*") {
		$file = Join-Path $Runtime ($rel.TrimStart("/") -replace "/", "\")
	} else {
		$file = Join-Path $webapp ($rel.TrimStart("/") -replace "/", "\")
	}

	if (Test-Path $file -PathType Leaf) {
		$bytes = [System.IO.File]::ReadAllBytes($file)
		$ext = [System.IO.Path]::GetExtension($file).ToLower()
		$ctx.Response.ContentType = $(if ($mime.ContainsKey($ext)) { $mime[$ext] } else { "application/octet-stream" })
		$ctx.Response.Headers.Add("Cache-Control", "no-store")
		$ctx.Response.ContentLength64 = $bytes.Length
		$ctx.Response.OutputStream.Write($bytes, 0, $bytes.Length)
	} else {
		$ctx.Response.StatusCode = 404
		$msg = [System.Text.Encoding]::UTF8.GetBytes("404 " + $rel)
		$ctx.Response.OutputStream.Write($msg, 0, $msg.Length)
	}
	$ctx.Response.OutputStream.Close()
}
$listener.Stop()
