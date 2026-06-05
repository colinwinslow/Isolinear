function Resolve-NodeTool {
    param(
        [Parameter(Mandatory = $true)]
        [ValidateSet("node", "npm", "npx")]
        [string]$ToolName
    )

    $CommandName = if ($ToolName -eq "node") { "node.exe" } else { "$ToolName.cmd" }
    $PathTool = Get-Command $CommandName -ErrorAction SilentlyContinue
    if ($PathTool) {
        return $PathTool.Source
    }

    $StandardInstallPath = Join-Path "C:\Program Files\nodejs" $CommandName
    if (Test-Path -LiteralPath $StandardInstallPath) {
        return $StandardInstallPath
    }

    $X86InstallPath = Join-Path "C:\Program Files (x86)\nodejs" $CommandName
    if (Test-Path -LiteralPath $X86InstallPath) {
        return $X86InstallPath
    }

    throw "Could not find $CommandName. Install Node.js LTS, reopen PowerShell, or add C:\Program Files\nodejs to PATH."
}
