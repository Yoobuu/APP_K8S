# backend/scripts/collect_hyperv_inventory.ps1
param(
    [Parameter(Mandatory=$true)][string]$HVHost,
    [ValidateSet('summary','detail','deep')][string]$Level = 'summary',
    [string]$VMName = $null,
    [switch]$SkipVhd,
    [switch]$SkipMeasure,
    [switch]$SkipKvp
)

$ErrorActionPreference = 'Stop'
$ProgressPreference    = 'SilentlyContinue'

Import-Module Hyper-V -ErrorAction Stop
Import-Module FailoverClusters -ErrorAction SilentlyContinue

# Defaults by level (switches win if explicitly passed)
if ($Level -eq 'summary') {
  $SkipVhd = $true
  $SkipMeasure = $true
  $SkipKvp = $true
}
elseif ($Level -eq 'detail') {
  # Allow overrides via switches
  if (-not $PSBoundParameters.ContainsKey('SkipVhd')) { $SkipVhd = $false }
  if (-not $PSBoundParameters.ContainsKey('SkipMeasure')) { $SkipMeasure = $false }
  if (-not $PSBoundParameters.ContainsKey('SkipKvp')) { $SkipKvp = $false }
}
else { # deep
  $SkipVhd = $false
  $SkipMeasure = $false
  $SkipKvp = $false
}

$DoVhd = -not $SkipVhd
$DoMeasure = -not $SkipMeasure
$DoKvp = -not $SkipKvp

# Datos de host/switch para deep
$globalSwitches = @()
if ($Level -eq 'deep') {
  try { $globalSwitches = Get-VMSwitch | Select-Object Name, Notes, SwitchType, NetAdapterInterfaceDescription } catch {}
}

$globalHostInfo = $null
if ($Level -eq 'deep') {
  try {
    $vmHost = Get-VMHost -ComputerName $HVHost -ErrorAction SilentlyContinue | Select-Object Name, LogicalProcessorCount, MemoryCapacity, VirtualMachineMigrationEnabled, Version
    # Uptime y uso CPU/Mem
    $uptimeSec = $null; $cpuHostPct = $null; $memHostPct = $null
    try {
      $os = Get-CimInstance -ClassName Win32_OperatingSystem -ComputerName $HVHost -ErrorAction Stop
      if ($os) {
        $uptimeSec = [int](([DateTime]::UtcNow) - $os.LastBootUpTime.ToUniversalTime()).TotalSeconds
        $memTotal = [int64]$os.TotalVisibleMemorySize * 1024
        $memFree  = [int64]$os.FreePhysicalMemory * 1024
        if ($memTotal -gt 0) { $memHostPct = [math]::Round((($memTotal - $memFree) / $memTotal) * 100, 2) }
      }
    } catch {}
    try {
      $cpuHostPct = [math]::Round((Get-Counter -Counter '\Processor(_Total)\% Processor Time').CounterSamples[0].CookedValue, 2)
    } catch {}

    # NICs físicas
    $nics = @()
    try {
      $nics = Get-NetAdapter -ErrorAction Stop | Select-Object Name, InterfaceDescription, MacAddress, Status, LinkSpeed
    } catch {}

    # Storage físico (si aplica)
    $storage = @()
    try {
      $storage = Get-PhysicalDisk -ErrorAction Stop | Select-Object FriendlyName, Size, MediaType, HealthStatus, OperationalStatus
    } catch {}

    $globalHostInfo = [pscustomobject]@{
      Name                          = $vmHost.Name
      LogicalProcessorCount         = $vmHost.LogicalProcessorCount
      MemoryCapacity                = $vmHost.MemoryCapacity
      VirtualMachineMigrationEnabled = $vmHost.VirtualMachineMigrationEnabled
      Version                       = $vmHost.Version
      UptimeSeconds                 = $uptimeSec
      CpuUsagePct                   = $cpuHostPct
      MemUsagePct                   = $memHostPct
      Nics                          = $nics
      Storage                       = $storage
    }
  } catch {}
}

$scvmmStorage = $null
if ($Level -eq 'deep') {
  try {
    if (Get-Command Get-SCStoragePool -ErrorAction SilentlyContinue) {
      $scvmmStorage = Get-SCStoragePool -ErrorAction SilentlyContinue | Select-Object Name, CapacityGB, FreeSpaceGB, HealthStatus
    }
  } catch {}
}

# --- Cluster (opcional si existe) ---
$clusterName = $null; $vmOwnerMap = @{}
try {
  $cluster = Get-Cluster -ErrorAction Stop
  $clusterName = $cluster.Name
  $vmGroups = Get-ClusterGroup | Where-Object GroupType -eq "VirtualMachine"
  foreach ($g in $vmGroups) { $vmOwnerMap[$g.Name] = $g.OwnerNode.Name }
} catch {}

# --- SO desde KVP (local) ---
function Get-HVGuestOSFromKVP {
  param([Microsoft.HyperV.PowerShell.VirtualMachine]$VM)
  if (-not $DoKvp) { return $null }
  try {
    $vmGuid = $VM.VMId.Guid
    $cs = Get-CimInstance -Namespace root\virtualization\v2 `
         -ClassName Msvm_ComputerSystem -Filter "Name='$vmGuid'" -ErrorAction Stop
    if (-not $cs) { return $null }
    $kvp = Get-CimAssociatedInstance -InputObject $cs -ResultClassName Msvm_KvpExchangeComponent -ErrorAction Stop
    if (-not $kvp) { return $null }
    foreach ($raw in $kvp.GuestIntrinsicExchangeItems) {
      try {
        [xml]$xml = $raw
        $name = $xml.INSTANCE.PROPERTY | Where-Object { $_.Name -eq 'Name' } | Select-Object -ExpandProperty VALUE
        if ($name -eq 'OSName') {
          $data = $xml.INSTANCE.PROPERTY | Where-Object { $_.Name -eq 'Data' } | Select-Object -ExpandProperty VALUE
          if ($data) { return [string]$data }
        }
      } catch {}
    }
    return $null
  } catch { return "Error KVP: $($_.Exception.Message)" }
}

function Get-Disks($vm) {
  if (-not $DoVhd) { return @() }
  $diskObjs=@()
  try {
    $drives = Get-VMHardDiskDrive -VM $vm -ErrorAction Stop
  } catch {
    return @(@{ Display = "Error listing drives: $($_.Exception.Message)"; Error = $_.Exception.Message })
  }

  foreach($hdd in $drives){
    $path = $hdd.Path
    $errorMsg = $null
    $size = $null
    $alloc = $null
    $pct = $null
    
    try {
       if ([string]::IsNullOrWhiteSpace($path)) {
          $errorMsg = "Path empty (Passthrough?)"
       } else {
          # Intento rápido de obtener tamaño de archivo (Allocated)
          if (Test-Path $path) {
            $file = Get-Item $path -ErrorAction SilentlyContinue
            if ($file) { $alloc = [math]::Round(($file.Length/1GB),2) }
          }

          # [OPTIMIZACION DE EMERGENCIA]
          # Comentamos Get-VHD porque está causando timeouts de >5min en hosts lentos/saturados.
          # Solo devolveremos el espacio usado (Allocated).
          
          # try {
          #   $v = Get-VHD -Path $path -ErrorAction Stop
          #   $size = [math]::Round(($v.Size/1GB),2)
          #   if ($size -gt 0 -and $alloc -ne $null) {
          #       $pct = [math]::Round(($alloc / $size)*100,2)
          #   }
          # } catch {
          #   $errorMsg = "VHD Header Unreadable"
          # }
       }
    } catch {
       $errorMsg = "Error: $($_.Exception.Message)"
    }
    
    $props = [ordered]@{
       Path = $path
       SizeGiB = $size
       AllocatedGiB = $alloc
       AllocatedPct = $pct
       Error = $errorMsg
    }
    
    # Si tenemos al menos el alloc, quitamos el error del display para que se vea el dato
    if ($alloc -ne $null) {
       $sizeText = if ($size) { $size } else { "???" }
       $props['Display'] = "$alloc GB / $sizeText GB"
    } elseif ($errorMsg) {
       $props['Display'] = "Error: $errorMsg"
    }

    $diskObjs += [pscustomobject]$props
  }
  return $diskObjs
}

function Get-NICInfo($vm, $PreLoadedNics=$null) {
  $vlanIds=@(); $ipList=@(); $networks=@()
  try {
    $nics = if ($PreLoadedNics) { $PreLoadedNics } else { Get-VMNetworkAdapter -VM $vm }
    foreach ($nic in $nics) {
      try {
        $vlan=Get-VMNetworkAdapterVlan -VMNetworkAdapter $nic
        if ($vlan) {
          if ($vlan.AccessVlanId){$vlanIds+=[int]$vlan.AccessVlanId}
          if ($vlan.TrunkVlanId){$vlanIds+=[int]$vlan.TrunkVlanId}
        }
      } catch {}
      if ($nic.IPAddresses){
        $ipList += $nic.IPAddresses | Where-Object { $_ -match '^\d{1,3}(\.\d{1,3}){3}$' }
      }
      if ($nic.SwitchName) { $networks += $nic.SwitchName }
    }
  } catch {}
  if ($vlanIds.Count -gt 0){$vlanIds=$vlanIds|Sort-Object -Unique}else{$vlanIds=@()}
  if ($ipList.Count  -eq 0){$ipList=@()}
  if ($networks.Count -gt 0){$networks=$networks|Sort-Object -Unique}else{$networks=@()}
  return @{ VLANs = $vlanIds; IPv4 = $ipList; Networks = $networks }
}

function Get-OneVM {
  param([string]$HVHost,[Microsoft.HyperV.PowerShell.VirtualMachine]$VM, $PreLoadedNics=$null)

  # vCPU y uso CPU (fallback Measure-VM)
  $vCPU = $null; try { $vCPU = (Get-VMProcessor -VM $VM).Count } catch {}
  $cpuUsagePct = $null
  try { $cpuUsagePct = $VM.CPUUsage } catch {}
  $measureDetail = $null
  if ($DoMeasure -and ($cpuUsagePct -eq $null -or $cpuUsagePct -eq 0 -or $Level -eq 'deep')) {
    try {
      $m = Measure-VM -ComputerName $HVHost -VMName $VM.Name -ErrorAction Stop
      if ($m.Processor.Average) { $cpuUsagePct = [math]::Round($m.Processor.Average,2) }
      if ($Level -eq 'deep') {
        $measureDetail = @{ Processor = $m.Processor; Memory = $m.Memory; Network = $m.NetworkAdapter; Disk = $m.Disk }
      }
    } catch {}
  }

  # RAM
  $ramMB  = $null; $ramDem = $null; $ramPct = $null
  try { $ramMB  = [int]($VM.MemoryAssigned/1MB) } catch {}
  try { $ramDem = [int]($VM.MemoryDemand/1MB)   } catch {}
  if ($ramMB -gt 0 -and $ramDem -ge 0) {
    $ramPct = [math]::Round(($ramDem / $ramMB)*100,2)
  }

  # NICs
  $nicInfo = Get-NICInfo -vm $VM -PreLoadedNics $PreLoadedNics

  # Compatibilidad (Version y Generation 1/2)
  $ver=$null; try { $ver=$VM.Version } catch {}
  $gen=$null; try { $gen=$VM.Generation } catch {}  # ← aquí tienes Generation 1 o 2

  # SO (KVP) y cluster
  $guestOS=$null
  if($VM.State -eq 'Running'){ $guestOS=Get-HVGuestOSFromKVP -VM $VM }
  $cluster = $null
  try {
    $grp = Get-ClusterGroup -Name ("Virtual Machine " + $VM.Name) -ErrorAction SilentlyContinue
    if ($grp) { $cluster = $grp.Cluster.Name }
  } catch {}

  # Discos
  $disks = Get-Disks -vm $VM

  # Checkpoints (deep)
  $checkpoints = @()
  if ($Level -eq 'deep') {
    try { $checkpoints = Get-VMSnapshot -VMName $VM.Name -ErrorAction SilentlyContinue | Select-Object Name, CreationTime, IsPaused, IsOffline, ParentSnapshotId } catch {}
  }

  # → SALIDA en el **esquema objetivo (inglés)** para no tocar schema.py
  [pscustomobject]@{
    HVHost         = $HVHost
    Name           = $VM.Name
    State          = $VM.State.ToString()
    vCPU           = [int]$vCPU
    CPU_UsagePct   = ($cpuUsagePct -as [double])
    RAM_MiB        = ($ramMB -as [int])
    RAM_Demand_MiB = ($ramDem -as [int])
    RAM_UsagePct   = ($ramPct -as [double])
    OS             = $guestOS
    Cluster        = $cluster
    VLAN_IDs       = @($nicInfo.VLANs)
    IPv4           = @($nicInfo.IPv4)
    Networks       = @($nicInfo.Networks)
    CompatHW       = @{ Version = $ver; Generation = $gen }
    Disks          = $disks
    OwnerNode      = $vmOwnerMap[$VM.Name]
    MeasureVM      = $measureDetail
    Switches       = $globalSwitches
    HostInfo       = $globalHostInfo
    Checkpoints    = $checkpoints
    SCVMMStorage   = $scvmmStorage
  }
}

# --- Recoger inventario del host indicado ---
$items = @()
try {
  $vmFilter = $null
  if ($VMName) { $vmFilter = $VMName -split ',' }
  if ($vmFilter) {
    $vms = Get-VM -ComputerName $HVHost -Name $vmFilter -ErrorAction Stop
  } else {
    $vms = Get-VM -ComputerName $HVHost -ErrorAction Stop
  }

  # Optimization: Pre-fetch NICs to avoid N+1 Get-VMNetworkAdapter calls
  $allNics = @{}
  if ($vms) {
      try {
         $rawNics = $vms | Get-VMNetworkAdapter -ErrorAction SilentlyContinue
         foreach ($n in $rawNics) {
            $nm = $n.VMName
            if (-not $allNics.ContainsKey($nm)) { $allNics[$nm] = @() }
            $allNics[$nm] += $n
         }
      } catch {}
  }

  foreach ($vm in $vms) { 
     $n = if ($allNics.ContainsKey($vm.Name)) { $allNics[$vm.Name] } else { $null }
     $items += Get-OneVM -HVHost $HVHost -VM $vm -PreLoadedNics $n 
  }
} catch {
  Write-Warning "Get-VM en $HVHost falló: $($_.Exception.Message)"
}

$items | ConvertTo-Json -Depth 6
