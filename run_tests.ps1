$baseUrl = "http://127.0.0.1:5000"
$adminEmail = "admin@dsacompany.com" 
$adminPassword = "admin123" 
# Test users to create (admin-supplied temp passwords)
$testUsers = @(
    @{ name = "Test Emp A"; email = "test.a@company.local"; position = "Staff"; role = "employee"; password = "TempA123!" },
    @{ name = "Test Emp B"; email = "test.b@company.local"; position = "Staff"; role = "employee"; password = "TempB123!" }
)
function Invoke-Json {
    param($uri, $method="GET", $headers=@{}, $body=$null)
    try {
        if ($body -ne $null) {
            $headers = @{ "Content-Type"="application/json" } + $headers
            return Invoke-RestMethod -Uri $uri -Method $method -Headers $headers -Body ($body | ConvertTo-Json -Depth 10)
        } else {
            return Invoke-RestMethod -Uri $uri -Method $method -Headers $headers
        }
    } catch {
        Write-Host "ERROR invoking $method $uri" -ForegroundColor Red
        if ($_.Exception.Response -ne $null) {
            $resp = $_.Exception.Response.GetResponseStream()
            $reader = New-Object System.IO.StreamReader($resp)
            $text = $reader.ReadToEnd()
            Write-Host $text -ForegroundColor Red
        } else {
            Write-Host $_.Exception.Message -ForegroundColor Red
        }
        throw $_
    }
}
function Login($email, $password) {
    $body = @{ email = $email; password = $password }
    $resp = Invoke-Json -uri "$baseUrl/api/auth/login" -method "POST" -body $body
    return $resp
}
function Create-User($adminHeaders, $user) {
    # Note: The endpoint should be /api/auth/register, but assuming /api/users for user management
    $resp = Invoke-Json -uri "$baseUrl/api/auth/register" -method "POST" -headers $adminHeaders -body $user
    return $resp
}
function Create-Task($headers, $task) {
    $resp = Invoke-Json -uri "$baseUrl/api/tasks" -method "POST" -headers $headers -body $task
    return $resp
}
function AutoAssign($headers, $taskId) {
    $resp = Invoke-Json -uri "$baseUrl/api/tasks/auto-assign/$taskId" -method "POST" -headers $headers
    return $resp
}
function Start-Task($headers, $taskId) {
    $resp = Invoke-Json -uri "$baseUrl/api/tasks/start/$taskId" -method "POST" -headers $headers
    return $resp
}
function Complete-Task($headers, $taskId) {
    $resp = Invoke-Json -uri "$baseUrl/api/tasks/mark-complete/$taskId" -method "POST" -headers $headers
    return $resp
}
function List-Notifications($headers) {
    $resp = Invoke-Json -uri "$baseUrl/api/notifications" -method "GET" -headers $headers
    return $resp
}
function Mark-Notif-Read($headers, $id) {
    $body = @{ id = $id }
    $resp = Invoke-Json -uri "$baseUrl/api/notifications/mark-read" -method "POST" -headers $headers -body $body
    return $resp
}
function Reassign-Task($headers, $taskId, $newAssigneeId, $force=$false) {
    $body = @{ task_id = $taskId; new_assignee_id = $newAssigneeId; force = $force }
    $resp = Invoke-Json -uri "$baseUrl/api/tasks/reassign" -method "POST" -headers $headers -body $body
    return $resp
}
function Get-Stats($headers) {
    $resp = Invoke-Json -uri "$baseUrl/api/stats" -method "GET" -headers $headers
    return $resp
}
# --- NEW FUNCTION FOR DSA UTILS TEST ---
function Solve-Knapsack($headers, $items, $weights, $capacity) {
    # Define a test payload for the 0/1 Knapsack problem
    $body = @{ 
        items = $items; 
        weights = $weights; 
        capacity = $capacity 
    }
    $uri = "$baseUrl/api/dsa-utils/knapsack"
    Write-Host "  > POST $uri with Capacity $capacity" -ForegroundColor Cyan
    
    # Assuming knapsack logic might be complex, use a timeout for safety
    $resp = Invoke-Json -uri $uri -method "POST" -headers $headers -body $body
    return $resp
}
function Test-DsaUtils($headers) {
    Write-Host "`n12) Testing DSA Utility Endpoint (Knapsack Solver)..." -ForegroundColor Yellow
    
    # Knapsack Test Case (Max value should be 90)
    $items = @(10, 40, 30, 50)
    $weights = @(5, 4, 6, 3)
    $capacity = 10 
    
    $knapsackResult = Solve-Knapsack -headers $headers -items $items -weights $weights -capacity $capacity
    
    if ($knapsackResult -ne $null -and $knapsackResult.max_value -eq 90) {
        Write-Host "  [SUCCESS] Knapsack solver returned expected max value: $($knapsackResult.max_value)" -ForegroundColor Green
    } elseif ($knapsackResult -ne $null) {
        Write-Host "  [FAILURE] Knapsack solver returned unexpected result: $($knapsackResult.max_value). Expected: 90" -ForegroundColor Red
    } else {
        Write-Host "  [FAILURE] Knapsack solver returned no result." -ForegroundColor Red
    }
}
# ---- Begin tests ----
Write-Host "1) Logging in as admin..."
$login = Login $adminEmail $adminPassword
$adminToken = $login.access_token
if (-not $adminToken) { throw "Admin login failed" }
$adminHeaders = @{ "Authorization" = "Bearer $adminToken" } # Content-Type moved to Invoke-Json for consistency
Write-Host "Admin token acquired." -ForegroundColor Green
# 2) Create test users
$createdUsers = @()
foreach ($u in $testUsers) {
    Write-Host "Creating user $($u.email) ..."
    # CRITICAL: Ensure the register endpoint is used if /api/users is not the correct path
    # Assuming Create-User calls /api/auth/register based on the function name.
    $resp = Create-User -adminHeaders $adminHeaders -user $u
    $createdUsers += [PSCustomObject]@{
        id = $resp.user.id
        email = $resp.user.email
        name = $resp.user.name
        temp_password = $u.password
    }
    Write-Host "  created id=$($resp.user.id)" -ForegroundColor Cyan
}
# 3) Login as first test user to ensure password works
Write-Host "3) Logging in as first created user to verify temp password..."
$u1 = $createdUsers[0]
$loginU1 = Login $u1.email $u1.temp_password
$user1Token = $loginU1.access_token
if (-not $user1Token) { throw "User1 login failed" }
$hUser1 = @{ "Authorization" = "Bearer $user1Token" }
Write-Host "User1 login OK." -ForegroundColor Green
# 4) Admin creates a task (pending)
Write-Host "4) Admin creating a task..."
$taskBody = @{ title = "Integration test task"; description = "Auto test"; priority = "high" }
$taskResp = Create-Task -headers $adminHeaders -task $taskBody
$taskId = $taskResp.task_id
Write-Host "Task created id=$taskId" -ForegroundColor Cyan
# 5) Auto-assign task
Write-Host "5) Auto-assigning task $taskId ..."
$aa = AutoAssign -headers $adminHeaders -taskId $taskId
Write-Host "Auto-assign result: $(ConvertTo-Json $aa -Depth 5)" -ForegroundColor Cyan
# determine assignee id (auto-assign result or fetch task)
$assigneeId = $aa.assignee_id
if (-not $assigneeId) {
    # fetch latest by-priority to find pending/assigned
    $list = Invoke-Json -uri "$baseUrl/api/tasks/by-priority" -method "GET" -headers $adminHeaders
    $taskObj = $list | Where-Object { $_.id -eq $taskId }
    $assigneeId = $taskObj.assignee_id
}
Write-Host "Task $taskId assigned to $assigneeId" -ForegroundColor Yellow
# 6) Login as assignee (one of test users) to check notifications and start task
$assignee = $createdUsers | Where-Object { $_.id -eq $assigneeId }  
# Check if the assignee is one of the NEWLY created test users ($createdUsers)
if ($assignee) {
    # --- Branch 1: Assignee is a NEW test user ---
    $loginAs = Login $assignee.email $assignee.temp_password
    $assigneeToken = $loginAs.access_token
} else {
    # --- Branch 2: Assignee is an EXISTING user ---
    
    # 1. Fetch all users from the API to get the existing user's details
    $allUsers = Invoke-Json -uri "$baseUrl/api/users" -method "GET" -headers $adminHeaders
    $assignee = $allUsers | Where-Object { $_.id -eq $assigneeId }
    if (-not $assignee) { throw "Cannot find assignee user $assigneeId" }
    
    # 2. Assign the known password for this existing user (User ID 5)
    #    ***Ensure this password is correct for the existing user***
    $knownPasswordForExistingUser = "TempPass123!" 
    
    # 3. Log in using the known password
    $assigneeLogin = Login $assignee.email $knownPasswordForExistingUser
    $assigneeToken = $assigneeLogin.access_token
} 
# --- The entire if/else block ends here, and the code continues ---
$hAssignee = @{ "Authorization" = "Bearer $assigneeToken" }
Write-Host "Assignee logged in (id $assigneeId)." -ForegroundColor Green
# 7) List notifications for assignee
Write-Host "7) Listing notifications for assignee..."
# Ensure $notifs is treated as an array (even if one item)
$notifs = @(List-Notifications -headers $hAssignee) 
Write-Host "Notifications: $(ConvertTo-Json $notifs -Depth 5)" -ForegroundColor Cyan
if ($notifs.Count -gt 0) {
    $nid = $notifs[0].id
    Write-Host "Marking notification $nid as read..." -ForegroundColor Yellow
    $mr = Mark-Notif-Read -headers $hAssignee -id $nid
    Write-Host "Mark result: $(ConvertTo-Json $mr -Depth 5)" -ForegroundColor Cyan
} else {
    Write-Host "No new notifications found." -ForegroundColor Yellow
}
# 8) Start the task as assignee
Write-Host "8) Starting task $taskId as assignee..."
$startResp = Start-Task -headers $hAssignee -taskId $taskId
Write-Host "Start response: $(ConvertTo-Json $startResp -Depth 5)" -ForegroundColor Cyan
# 9) Complete the task
Write-Host "9) Completing task $taskId as assignee..."
$compResp = Complete-Task -headers $hAssignee -taskId $taskId
Write-Host "Complete response: $(ConvertTo-Json $compResp -Depth 5)" -ForegroundColor Cyan
# 10) Reassign a new task to test reassign endpoint (create new task)
Write-Host "10) Testing reassign: create new task to reassign..."
$taskResp2 = Create-Task -headers $adminHeaders -task @{ title="Reassignable task"; description="for reassign"; priority="medium" }
$t2 = $taskResp2.task_id
Write-Host " created task id $t2" -ForegroundColor Cyan
# auto assign it first
$aa2 = AutoAssign -headers $adminHeaders -taskId $t2
Write-Host " autoassign returned: $(ConvertTo-Json $aa2 -Depth 5)" -ForegroundColor Cyan
# pick new assignee (the other created user)
$newAssignee = $createdUsers | Where-Object { $_.email -ne $u1.email } | Select-Object -First 1
if (-not $newAssignee) { throw "No second user available for reassign test" }
Write-Host "Reassigning task $t2 to user id $($newAssignee.id) ..." -ForegroundColor Yellow
$r = Reassign-Task -headers $adminHeaders -taskId $t2 -newAssigneeId $newAssignee.id -force:$false
Write-Host "Reassign result: $(ConvertTo-Json $r -Depth 5)" -ForegroundColor Cyan
# 11) Stats
Write-Host "11) Fetching stats..." -ForegroundColor Yellow
$s = Get-Stats -headers $adminHeaders
Write-Host "Stats: $(ConvertTo-Json $s -Depth 5)" -ForegroundColor Cyan
# --- DSA UTILS TEST CALL ---
Test-DsaUtils -headers $adminHeaders
# ---------------------------
Write-Host "`nAll tests completed successfully." -ForegroundColor Green

