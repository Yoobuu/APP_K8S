from .context import CollectorContext
from .vinfo import collect as collect_vinfo
from .vcpu import collect as collect_vcpu
from .vmemory import collect as collect_vmemory
from .vdisk import collect as collect_vdisk
from .vpartition import collect as collect_vpartition
from .vnetwork import collect as collect_vnetwork
from .vcd import collect as collect_vcd
from .vusb import collect as collect_vusb
from .vsnapshot import collect as collect_vsnapshot
from .vtools import collect as collect_vtools
from .vsource import collect as collect_vsource
from .vrp import collect as collect_vrp
from .vcluster import collect as collect_vcluster
from .vhost import collect as collect_vhost
from .vhba import collect as collect_vhba
from .vnic import collect as collect_vnic
from .vswitch import collect as collect_vswitch
from .vport import collect as collect_vport
from .dvswitch import collect as collect_dvswitch
from .dvport import collect as collect_dvport
from .vsc_vmk import collect as collect_vsc_vmk
from .vdatastore import collect as collect_vdatastore
from .vmultipath import collect as collect_vmultipath
from .vlicense import collect as collect_vlicense
from .vfileinfo import collect as collect_vfileinfo
from .vhealth import collect as collect_vhealth
from .vmetadata import collect as collect_vmetadata

COLLECTORS = {
    "vInfo": collect_vinfo,
    "vCPU": collect_vcpu,
    "vMemory": collect_vmemory,
    "vDisk": collect_vdisk,
    "vPartition": collect_vpartition,
    "vNetwork": collect_vnetwork,
    "vCD": collect_vcd,
    "vUSB": collect_vusb,
    "vSnapshot": collect_vsnapshot,
    "vTools": collect_vtools,
    "vSource": collect_vsource,
    "vRP": collect_vrp,
    "vCluster": collect_vcluster,
    "vHost": collect_vhost,
    "vHBA": collect_vhba,
    "vNIC": collect_vnic,
    "vSwitch": collect_vswitch,
    "vPort": collect_vport,
    "dvSwitch": collect_dvswitch,
    "dvPort": collect_dvport,
    "vSC_VMK": collect_vsc_vmk,
    "vDatastore": collect_vdatastore,
    "vMultiPath": collect_vmultipath,
    "vLicense": collect_vlicense,
    "vFileInfo": collect_vfileinfo,
    "vHealth": collect_vhealth,
    "vMetaData": collect_vmetadata,
}

__all__ = ["CollectorContext", "COLLECTORS"]
