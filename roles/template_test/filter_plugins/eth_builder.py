# -*- coding: utf-8 -*-
# Copyright 2020 Red Hat
# GNU General Public License v3.0+
# (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)


"""
flatten a complex object to dot bracket notation
"""
from __future__ import absolute_import, division, print_function
from dataclasses import dataclass, asdict, field
from typing import Optional

__metaclass__ = type

import random
from typing import List


from ansible.errors import AnsibleFilterError
from enum import Enum
from netutils.interface import split_interface


class DesignationVLANMapping(Enum):
    """Enum for mapping the designation to a untagged VLAN for primary interfaces Et1-48."""

    # Ethernet1-24 VLANs
    """The DEFAULT native VLAN."""
    DEFAULT_NATIVE = 999
    """The ESX VLAN also the default native VLAN for primary server interfaces."""
    BM_ESX = 100
    """The production VLAN."""
    BM_PROD = 200
    """The non production VLAN."""
    BM_NON_PROD = 300
    """The ESX server DMZ VLAN."""
    BM_ESX_DMZ = 600
    """The rack mounted Workstation server in Workstation VLAN."""
    WORKSTATION = 250

    # Ethernet25-48 VLANs
    # No LACP Fallback, so Port-Channels leverage the VLAN & not Ethernet Interfaces EXCEPT for un-bonded interfaces.
    """The A side market data multicast VLAN."""
    BM_MD_NON_BOND_A = 700
    """The B side market data multicast VLAN."""
    BM_MD_NON_BOND_B = 701


@dataclass
class BaseInterface:
    """The base interface, contains common attributes."""

    """The interface name"""
    name: str

    """The interface description"""
    description: Optional[str] = field(default=None)
    """The interface shutdown status"""
    shutdown: bool = field(default=False)

    #def __post__init__(self):
    #    """Post initialize the interface.
    #
    #    Extract the name from the number
    #    """
    #    #self.number = int(self.name.replace("Ethernet", ""))

    def to_keyed_dict(self):
        """Convert the interface to a dict keyed with interface name."""
        details = asdict(self)
        return {details.pop("name"): details}


@dataclass
class ChannelGroup:

    """The chanel group id determines the Port-Channel membership."""
    id: int = -1
    """Set the channel group mode."""
    mode: str = "active"


@dataclass
class LACPInterface(BaseInterface):
    """The LACP interface config, contains common attributes for LACP."""

    """Set channel group details."""
    channel_group: ChannelGroup = ChannelGroup(id=channel_group_id)

    #def __post_init__(self):
    #    channel_group_id = -1
    #    self.channel_group = ChannelGroup(id=channel_group_id)

    #@property
    #def number(self):
    #    return self.name.replace("Ethernet", "")


@dataclass
class PrimaryLACPBaseInterface(LACPInterface):
    """Sets the common config for the primary interface (Et1-24) for LACP"""

    """The interface spanning tree portfast status"""
    spanning_tree_portfast: Optional[str] = field(default="edge")
    """The interface type (switched or routed)"""
    type: str = field(default="switched")


@dataclass
class TrunkInterface(BaseInterface):
    """The trunk interface config, contains common attributes for trunk ports."""

    """The switchport mode used by the interface"""
    mode: str = "trunk"
    """The native / untagged vlan on the interface"""
    native_vlan: int = field(default=DesignationVLANMapping['BM_ESX'].value)
    """The trunk groups allowed on the interface"""
    trunk_groups: List = field(default_factory=lambda: ["SERVER"])


@dataclass
class NOLACPTrunkInterface(TrunkInterface):
    """The LACP interface config with NO LACP, contains common attributes for these ports."""

    """The interface spanning tree portfast status"""
    spanning_tree_portfast: Optional[str] = field(default="edge")
    """The interface type (switched or routed)"""
    type: str = field(default="switched")


@dataclass
class PrimaryTrunkLACPFallbackInterface(PrimaryLACPBaseInterface):
    """The LACP interface for primary interfaces (Et1-24) config with LACP fallback, contains common attributes for these ports."""

    """The switchport mode used by the interface"""
    mode: str = "trunk"
    """The native / untagged vlan on the interface"""
    native_vlan: int = field(default=DesignationVLANMapping['BM_ESX'].value)
    """The trunk groups allowed on the interface"""
    trunk_groups: List = field(default_factory=lambda: ["SERVER"])


@dataclass
class AccessInterface(BaseInterface):
    """The base access primary interface."""

    """The access vlan"""
    vlans: int = -1
    """The port mode"""
    mode: str = "access"
    """The interface spanning tree portfast status"""
    spanning_tree_portfast: Optional[str] = field(default="edge")
    """The interface type (switched or routed)"""
    type: str = field(default="switched")

@dataclass
class SecondaryAccessInterface(BaseInterface):
    """The access secondary interface."""

    """The interface shutdown status"""
    shutdown: bool = True

def _eth_builder(data):
    result = {}
    non_default_switchport_list = data["rack_non_default_switchports"].keys()
    switch_letter = data["inventory_hostname"][-1].upper()
    for interface in data["interfaces"]:

        if interface["type"] == "25GBASE_SFP28":
            interface_number = int(split_interface(interface["name"])[1])

            if interface["name"] in non_default_switchport_list:
                non_default_switchport = data["rack_non_default_switchports"][interface["name"]]
            else:
                non_default_switchport = {'designation': 'BM_ESX', 'connected_host': ''}

            if 1 <= interface_number <= 24:
                if non_default_switchport["designation"].startswith("BM_"):
                    if non_default_switchport["designation"] == "BM_ESX_VOICE":
                        obj_interface = NOLACPTrunkInterface(
                            description=non_default_switchport["connected_host"],
                            name=interface["name"],
                            native_vlan=DesignationVLANMapping["BM_ESX"].value,
                            trunk_groups=["SERVER"],
                        )
                    else:
                        if "DMZ" in non_default_switchport["designation"]:
                            trunk_groups = ["DMZ_SERVER"]
                        else:
                            trunk_groups = ["SERVER"]
                        obj_interface = PrimaryTrunkLACPFallbackInterface(
                            channel_group_id=interface_number,
                            description=non_default_switchport["connected_host"],
                            name=interface["name"],
                            native_vlan=DesignationVLANMapping[non_default_switchport["designation"] ].value,
                            trunk_groups=trunk_groups,
                        )

                elif non_default_switchport["designation"] == "WORKSTATION":
                    obj_interface = AccessInterface(
                      description=non_default_switchport["connected_host"],
                      name=interface["name"],
                      vlans=DesignationVLANMapping[non_default_switchport["designation"] ].value,
                    )

                else:
                    obj_interface = PrimaryTrunkLACPFallbackInterface(
                        channel_group_id=interface_number,
                        description=non_default_switchport["connected_host"] ,
                        name=interface["name"],
                        native_vlan=DesignationVLANMapping[non_default_switchport["designation"] ].value,
                        trunk_groups=["SERVER"],
                    )

            elif 25 <= interface_number <= 48:
                if non_default_switchport["designation"] == "WORKSTATION":
                    obj_interface = BaseInterface(
                      description=non_default_switchport["connected_host"],
                      name=interface["name"],
                      shutdown=True,
                      )
                elif non_default_switchport["designation"] == "BM_ESX_VOICE":
                    obj_interface = NOLACPTrunkInterface(
                        description=non_default_switchport["connected_host"],
                        name=interface["name"],
                        native_vlan=DesignationVLANMapping["DEFAULT_NATIVE"].value,
                        trunk_groups = ["ISCSI"],
                    )
                elif non_default_switchport["designation"] == "BM_MD_NON_BOND":
                    vlan_designation = "BM_MD_NON_BOND_" + switch_letter
                    obj_interface = AccessInterface(
                      description=non_default_switchport["connected_host"],
                      name=interface["name"],
                      vlans=DesignationVLANMapping[vlan_designation].value,
                      )
                else:
                    obj_interface = LACPInterface(
                        channel_group_id=interface_number,
                        description=non_default_switchport["connected_host"],
                        name=interface["name"],
                    )

            result.update(obj_interface.to_keyed_dict())
    return result


class FilterModule(object):
    def filters(self):
        return {"eth_builder": _eth_builder}
