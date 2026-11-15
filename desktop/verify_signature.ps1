param([Parameter(Mandatory=$true)][string]$Installer)
$ErrorActionPreference = 'Stop'
$s = Get-AuthenticodeSignature -LiteralPath $Installer
$f = (Get-Item -LiteralPath $Installer).VersionInfo
@{
  Status = $s.Status.ToString()
  Thumbprint = if ($s.SignerCertificate) { $s.SignerCertificate.Thumbprint } else { '' }
  FileVersion = $f.FileVersion
  ProductVersion = $f.ProductVersion
} | ConvertTo-Json -Compress
