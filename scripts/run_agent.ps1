param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('onboarding', 'delivery', 'dashboard', 'tasks')]
    [string]$Component,
    [ValidateSet('Enterprise', 'Growth', 'the expensive one')]
    [string]$Answer = 'Growth',
    [string]$GmailQuery,
    [string]$RunId,
    [ValidateSet('all', 'Kickoff', 'Data Migration', 'Configuration', 'Go-Live')]
    [string]$Phase = 'all'
)

# Run each continuous component in its own terminal; Ctrl+C stops it.
# Real Gmail/Slack; voice and Rocketlane remain simulated.
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Project Python environment missing: .venv\Scripts\python.exe'
}
$previousQuery = $env:GMAIL_QUERY
Push-Location -LiteralPath $projectRoot
try {
    switch ($Component) {
        'onboarding' {
            if ($GmailQuery) { $env:GMAIL_QUERY = $GmailQuery }
            else { Remove-Item Env:GMAIL_QUERY -ErrorAction SilentlyContinue }
            & $pythonPath -u -m app.main --gmail-slack-demo --db local-worker.db worker --interval 15 --answer $Answer
        }
        'delivery' {
            & $pythonPath -u -m app.delivery --db demo-local-worker.db worker --interval 60
        }
        'dashboard' {
            & $pythonPath -u -m app.dashboard --db demo-local-worker.db --port 8080
        }
        'tasks' {
            if (-not $RunId) { throw '-RunId is required for task simulation. Stop the delivery worker first.' }
            & $pythonPath -m scripts.simulate_project_tasks $RunId --db demo-local-worker.db --phase $Phase
        }
    }
    if ($LASTEXITCODE -ne 0) { throw "Agent component exited with code $LASTEXITCODE" }
}
finally {
    $env:GMAIL_QUERY = $previousQuery
    Pop-Location
}
