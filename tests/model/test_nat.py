from typing import List

from pycroft.model import nat, session
from pycroft.model.nat import NATDomain, Translation
from tests import FactoryDataTestBase
from tests.factories import ConfigFactory, UserFactory
from tests.factories.nat import NatDomainFactory, OutsideIpAddressFactory, \
    InsideNetworkFactory


class NatTestBase(FactoryDataTestBase):
    def create_factories(self):
        super().create_factories()
        ConfigFactory.create()
        self.nat_domain = NatDomainFactory()
        # TODO create a pool of `InsideNetwork`s and `OutsideIps`
        self.in_nets = InsideNetworkFactory.create_batch(nat_domain=self.nat_domain)


class TrivialNatModelTestCase(NatTestBase):
    def create_factories(self):
        super().create_factories()

    def test_one_natdomain(self):
        doms: List[NATDomain] = NATDomain.q.all()
        self.assertEqual(len(doms), 1)
        dom = doms[0]
        self.assertEqual(dom.name, self.nat_domain.name)

    def test_translation_references(self):
        out_ip = OutsideIpAddressFactory.build(nat_domain=self.nat_domain)
        in_net: nat.InsideNetwork
        in_net = InsideNetworkFactory.build(nat_domain=self.nat_domain)

        t = Translation(
            outside_address_rel=out_ip,
            inside_network=in_net.ip_network,
        )

        # act
        session.session.add_all([out_ip, in_net, t])
        session.session.commit()

        # assert
        self.assertEqual(Translation.q.count(), 1)

    def test_translation_rel_wth_proper_subnet(self):
        # TODO test that a translation with
        pass

    def test_translation_rel_with_bad_subnet(self):
        # TODO test that
        pass



class SimpleNatModelTestCase(NatTestBase):
    def create_factories(self):
        super().create_factories()
        self.user = UserFactory.create()
        self.outside_ip = OutsideIpAddressFactory(owner=self.user,
                                                  nat_domain=self.nat_domain)
        # TODO later check that this doesn't work because every outside_ip needs a translation
        # TODO add a pool of inside networks

    def test_forwardings_correct(self):
        domain: NATDomain = NATDomain.q.one()
        self.assertEqual(domain.name, self.nat_domain.name)

    def test_gateway_must_be_in_network(self):
        pass

# TODO test a translation
# TODO visit _all_ relationships to make sure the joins work
