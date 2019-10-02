import ipaddress

from factory import Sequence, SubFactory, Faker
from factory.fuzzy import FuzzyChoice

from pycroft.model.nat import NATDomain, OutsideIPAddress
from pycroft.model.nat import InsideNetwork, Translation, Forwarding, \
    DHCPHostReservation
from .base import BaseFactory


class NatDomainFactory(BaseFactory):
    class Meta:
        model = NATDomain

    name = Sequence(lambda n: f"NAT Domain {n + 1}")


class OutsideIpAddressFactory(BaseFactory):
    class Meta:
        model = OutsideIPAddress

    nat_domain = SubFactory(NatDomainFactory)
    ip_address = Faker('ipv4', network=False)
    owner = None


class InsideNetworkFactory(BaseFactory):
    # TODO this should be filled with all available inside networks
    class Meta:
        model = InsideNetwork

    nat_domain = SubFactory(NatDomainFactory)
    ip_network = Sequence(lambda n: ipaddress.ip_network(f'100.64.{n}.0/24'))
    gateway = Sequence(lambda n: ipaddress.ip_address(f'100.64.{n}.1'))


class TranslationFactory(BaseFactory):
    class Meta:
        model = Translation

    # NB: nat_domain won't be set, because that happens implicitly by one of the
    # relationships

    # 6: TCP, 17: UDP
    # see https://en.wikipedia.org/wiki/List_of_IP_protocol_numbers
    protocol = FuzzyChoice([6, 17])
    outside_address_rel = SubFactory(OutsideIpAddressFactory)

    # NB: remember that `inside_network` is *not* an fkey, but coupled via <<=!
    inside_network = None  # better set this manually
    owner = None


class ForwardingFactory(BaseFactory):
    class Meta:
        model = Forwarding

    nat_domain = SubFactory(NatDomainFactory)
    protocol = FuzzyChoice([6, 17])
    outside_ip_address = SubFactory(OutsideIpAddressFactory)

    # TODO fill in the rest


class DhcpHostReservationFactory(BaseFactory):
    class Meta:
        model = DHCPHostReservation

    # TODO create to taste. OFC necessary when creating forwardings.
