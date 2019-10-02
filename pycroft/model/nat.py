from sqlalchemy import CheckConstraint, Column, ForeignKey, \
    Integer, SmallInteger, String, Text, \
    UniqueConstraint, func, and_, ForeignKeyConstraint
from sqlalchemy.orm import relationship, backref, foreign

from .base import IntegerIdModel, ModelBase
from .types import IPAddress, MACAddress, IPNetwork
from .user import User


def single_ipv4_constraint(col: Column):
    return CheckConstraint(and_(func.family(col) == 4, func.masklen(col) == 32))


class NATDomain(IntegerIdModel):
    name = Column(String, nullable=False)


def nat_domain_id_column(pkey=True):
    return Column(
        Integer,
        ForeignKey(NATDomain.id, ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=pkey,
        nullable=False
    )


class DHCPHostReservation(ModelBase):
    """An assignment of a mac to an internal IP

    A constraint trigger verifies that an InsideNetwork exists for a given value
    for `ip`
    """
    nat_domain_id = nat_domain_id_column()
    nat_domain = relationship(NATDomain)

    ip = Column(IPAddress, primary_key=True, nullable=False)
    mac = Column(MACAddress, nullable=False)

    # TODO: A relationship to an `InsideNetwork` comparing (ip, ≤), (dom, ==)

    __table_args__ = (
        single_ipv4_constraint(col=ip),
    )


class InsideNetwork(ModelBase):
    """An internal network, not necessarily assigned to a user.

    Unique only up to NAT Domain (hence the composite primary key).

    The `ip_network` typically is in a range below 100.64.x.x
    """
    nat_domain_id = nat_domain_id_column()
    nat_domain = relationship(NATDomain)

    ip_network = Column(IPNetwork, primary_key=True, nullable=False)
    gateway = Column(IPAddress, nullable=False)


class OutsideIPAddress(ModelBase):
    """A natted, public IP address (unique only up to NatDomain)"""
    nat_domain_id = nat_domain_id_column()
    nat_domain = relationship(NATDomain)

    ip_address = Column(IPAddress, primary_key=True, nullable=False)
    owner_id = Column(Integer, ForeignKey(User.id))
    owner = relationship(User, backref="outside_ip_addresses")

    __table_args__ = (
        single_ipv4_constraint(col=ip_address),
    )


class Translation(ModelBase):
    """A translation between an internal network and an outside ip.

    Translation has a composite foreign key only(!) to OutsideIPAddress
    (on nat_domain and outside_address), and therefore transitively a
    relationship to a NatDomain.

    It is weakly coupled (i.e., not by a ForeignKeyConstraint) to
    an InsideIPNetwork by a function verifying that an InsideNetwork tuple
    with the same ip network and NatDomain exists.
    """
    nat_domain_id = nat_domain_id_column()
    # nat_domain implicitly set via `outside_address_rel`
    nat_domain = relationship(NATDomain, viewonly=True)

    outside_address = Column(IPAddress, primary_key=True, nullable=False)
    outside_address_rel = relationship(OutsideIPAddress)

    # CAREFUL: this is NOT a (composite, w_ domain) FKey,
    # but instead WEAKLY coupled, because we want inet-containment
    # instead of equality!
    inside_network = Column(IPNetwork, nullable=False)
    inside_network_rel = relationship(
        InsideNetwork,
        primaryjoin=and_(
            foreign(nat_domain_id) == InsideNetwork.nat_domain_id,
            foreign(inside_network).op("<<=")(InsideNetwork.ip_network),
        ),
        viewonly=True,
    )

    owner = relationship(User,
                         secondary=OutsideIPAddress.__table__,
                         backref="translations")

    __table_args__ = (
        single_ipv4_constraint(col=outside_address),
        ForeignKeyConstraint(
            (nat_domain_id, outside_address),
            (OutsideIPAddress.nat_domain_id, OutsideIPAddress.ip_address),
            ondelete="CASCADE", onupdate="CASCADE"
        ),
    )


class Forwarding(ModelBase):
    nat_domain_id = nat_domain_id_column(pkey=False)
    # implicitly set by `outside_address_rel`
    nat_domain = relationship(NATDomain, viewonly=True)

    outside_address = Column(IPAddress, nullable=False)
    outside_address_rel = relationship(OutsideIPAddress)
    outside_port = Column(Integer)

    inside_address = Column(IPAddress, nullable=False)
    # TODO FKey to DHCP Host Reservation
    inside_port = Column(Integer)

    protocol = Column(SmallInteger, nullable=False)

    comment = Column(Text)

    owner_id = Column(Integer, ForeignKey(User.id, ondelete="CASCADE"),
                      nullable=False)
    owner = relationship(User, backref=backref("forwardings",
                                               cascade="all, delete-orphan"))

    # This is not actually a PKEY in the database, it is just convenient for
    # sqlalchemy for technical reasons.
    __mapper_args__ = {
        'primary_key': (nat_domain_id, outside_address, protocol, outside_port),
    }

    __table_args__ = (
        UniqueConstraint(nat_domain_id, outside_address, protocol, outside_port),
        ForeignKeyConstraint(
            (nat_domain_id, outside_address),
            (OutsideIPAddress.nat_domain_id, OutsideIPAddress.ip_address),
            ondelete="CASCADE", onupdate="CASCADE"
        )
    )
