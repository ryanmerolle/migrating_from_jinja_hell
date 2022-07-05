# Copyright 2020 Red Hat
# GNU General Public License v3.0+
# (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)


"""
flatten a complex object to dot bracket notation
"""


import contextlib

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from netutils.interface import split_interface


# pylint: disable=invalid-name
# pylint: enable=invalid-name


class DesignationVLANMapping(Enum):
    """Enum for mapping the designation to a untagged VLAN for interfaces Et1-48."""

    # Ethernet1-24 VLANs
    """The DEFAULT native VLAN."""
    DEFAULT_NATIVE = 999
    """The ESX VLAN also the default native VLAN for low interfaces."""
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
    # No LACP Fallback, so Port-Channels leverage the VLAN & not Ethernet Interfaces
    # EXCEPT for un-bonded interfaces.
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

    def to_keyed_dict(self):
        """Convert the interface to a dict keyed with interface name."""
        details = asdict(self)

        """Delete channel_group_id from dictionary."""
        with contextlib.suppress(KeyError):
            del details["channel_group_id"]
        """output the name field as the dictionary name"""
        return {details.pop("name"): details}


@dataclass
class ChannelGroup:

    """The chanel group id determines the Port-Channel membership."""

    id: int = -1  # pylint: disable=invalid-name
    """Set the channel group mode."""
    mode: str = "active"


@dataclass
class LACPInterface(BaseInterface):
    """The LACP interface config, contains common attributes for LACP."""

    """The chanel group id determines the Port-Channel membership."""
    channel_group_id: int = -1
    """Set the channel group mode."""
    channel_group: ChannelGroup = ChannelGroup()

    def __post_init__(self):
        """Post initalize the interface."""
        self.channel_group = ChannelGroup(id=self.channel_group_id)


@dataclass
class LowLACPBaseInterface(LACPInterface):
    """Sets the common config for the low interface (Et1-24) for LACP"""

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
    native_vlan: int = field(default=DesignationVLANMapping["BM_ESX"].value)
    """The trunk groups allowed on the interface"""
    trunk_groups: List = field(default_factory=lambda: ["SERVER"])
    """The interface spanning tree portfast status"""
    spanning_tree_portfast: Optional[str] = field(default="edge")
    """The interface type (switched or routed)"""
    type: str = field(default="switched")


@dataclass
class LowTrunkLACPFallbackInterface(LowLACPBaseInterface):
    """The LACP interface for low interfaces.

    Eth1-24, config with LACP fallback, contains common attributes for these ports.
    """

    """The switchport mode used by the interface"""
    mode: str = "trunk"
    """The native / untagged vlan on the interface"""
    native_vlan: int = field(default=DesignationVLANMapping["BM_ESX"].value)
    """The trunk groups allowed on the interface"""
    trunk_groups: List = field(default_factory=lambda: ["SERVER"])


@dataclass
class AccessInterface(BaseInterface):
    """The base access low interface."""

    """The access vlan"""
    vlans: int = -1
    """The port mode"""
    mode: str = "access"
    """The interface spanning tree portfast status"""
    spanning_tree_portfast: Optional[str] = field(default="edge")
    """The interface type (switched or routed)"""
    type: str = field(default="switched")


@dataclass
class PortBuilder:
    """Build the port."""

    """The interface description"""
    description: str
    """The interface designation"""
    designation: str
    """The complete interface"""
    interface: Dict
    """The interface number"""
    interface_number: int
    "The switch letter"
    switch_letter: str

    def build(self):
        """Build the port.

        Use the designation to lookup a function withing this class or default.
        """
        builder = getattr(self, f"_{self.designation.lower()}", self._default)
        return builder()


@dataclass
class LowPortBuilder(PortBuilder):
    """Build the low (Ethernet1-24) port."""

    "The trunk groups allowed on the interface"
    trunk_groups: Optional[List]

    def _bm_esx_voice(self):
        """Build the high port for the ESX voice interface."""
        interface = TrunkInterface(
            description=self.description,
            name=self.interface["name"],
            native_vlan=DesignationVLANMapping["BM_ESX"].value,
            trunk_groups=self.trunk_groups,
        )
        return interface

    def _default(self):
        """Build the high port for the default interface."""
        interface = LowTrunkLACPFallbackInterface(
            channel_group_id=self.interface_number,
            description=self.description,
            name=self.interface["name"],
            native_vlan=DesignationVLANMapping[self.designation].value,
            trunk_groups=self.trunk_groups,
        )
        return interface

    def _workstation(self):
        """Build the low port for the workstation interface."""
        interface = AccessInterface(
            description=self.description,
            name=self.interface["name"],
            vlans=DesignationVLANMapping[self.designation].value,
        )
        return interface


@dataclass
class HighPortBuilder(PortBuilder):
    """Build the high (Ethernet25-48) port."""

    def _bm_esx_voice(self):
        """Build the high port for the ESX voice interface."""
        interface = TrunkInterface(
            description=self.description,
            name=self.interface["name"],
            native_vlan=DesignationVLANMapping["DEFAULT_NATIVE"].value,
            trunk_groups=["ISCSI"],
        )
        return interface

    def _bm_md_non_bond(self):
        """Build the high port for the market data interface."""
        vlan_designation = f"BM_MD_NON_BOND_{self.switch_letter}"
        interface = AccessInterface(
            description=self.description,
            name=self.interface["name"],
            vlans=DesignationVLANMapping[vlan_designation].value,
        )
        return interface

    def _default(self):
        """Build the high port for the default interface."""
        interface = LACPInterface(
            channel_group_id=self.interface_number,
            description=self.description,
            name=self.interface["name"],
        )
        return interface

    def _workstation(self):
        """Build the high port for the workstation interface. Sets a description & shuts it down."""
        interface = BaseInterface(
            description=self.description,
            name=self.interface["name"],
            shutdown=True,
        )
        return interface


def _eth_builder_2(data):
    """The ethernet interface configuration builder function."""
    result = {}
    switch_letter = data["inventory_hostname"][-1].upper()
    for interface in data["interfaces"]:
        if interface["type"] != "25GBASE_SFP28":
            continue  # move on quick, reduces the indent of the rest of the function

        interface_number = int(split_interface(interface["name"])[1])

        if interface["name"] in data["rack_non_default_switchports"].keys():
            non_default_switchport = data["rack_non_default_switchports"][
                interface["name"]
            ]
        else:
            non_default_switchport = {"designation": "BM_ESX", "connected_host": ""}

        if (
            1 <= interface_number <= 24
        ):  # "low ports" refer to Et1-24 which are the primary interfaces to servers.
            if "DMZ" in non_default_switchport["designation"]:
                trunk_groups = ["DMZ_SERVER"]
            else:
                trunk_groups = ["SERVER"]

            builder = LowPortBuilder(
                description=non_default_switchport["connected_host"],
                designation=non_default_switchport["designation"],
                interface=interface,
                interface_number=interface_number,
                switch_letter=switch_letter,
                trunk_groups=trunk_groups,
            )
            obj_interface = builder.build()

        # "high ports" refer to Et25-48 which are the dedicated iSCSI
        # or multicast interfaces to servers.
        elif 25 <= interface_number <= 48:
            builder = HighPortBuilder(
                description=non_default_switchport["connected_host"],
                designation=non_default_switchport["designation"],
                interface=interface,
                interface_number=interface_number,
                switch_letter=switch_letter,
            )
            obj_interface = builder.build()

        result.update(obj_interface.to_keyed_dict())
    return result


class FilterModule:
    """The required class for filter plugin registration."""

    def filters(self):
        """Define the filters to register."""
        return {"eth_builder_2": _eth_builder_2}
