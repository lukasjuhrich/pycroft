from datetime import datetime, timedelta

from pycroft.model import session
from pycroft.model import hades
from pycroft.model.net import VLAN
from tests import FactoryDataTestBase
from tests.factories import PropertyGroupFactory, MembershipFactory, UserWithHostFactory, \
    SwitchFactory, PatchPortFactory


class HadesTestBase(FactoryDataTestBase):
    def create_factories(self):
        self.user = UserWithHostFactory.create()
        self.network_access_group = PropertyGroupFactory.create(
            name="Member",
            granted={'network_access'},
        )
        self.payment_in_default_group = PropertyGroupFactory.create(
            name="Blocked (finance)",
            granted={'payment_in_default'},
            denied={'network_access'},
        )
        self.traffic_limit_exceeded_group = PropertyGroupFactory.create(
            name="Blocked (traffic)",
            granted={'traffic_limit_exceeded'},
            denied={'network_access'},
        )

        # the user's room needs to be connected to provide `nasipaddress` and `nasportid`
        self.switch = SwitchFactory.create(host__owner=self.user)
        PatchPortFactory.create_batch(2, patched=True, switch_port__switch=self.switch,
                                      # This needs to be the HOSTS room!
                                      room=self.user.hosts[0].room)

        MembershipFactory.create(user=self.user, group=self.network_access_group,
                                 begins_at=datetime.now() + timedelta(-1),
                                 ends_at=datetime.now() + timedelta(1))

        session.session.execute(hades.radius_property.insert(values=[
            ('payment_in_default',),
            ('traffic_limit_exceeded',),
        ]))


class HadesViewTest(HadesTestBase):
    def test_radcheck(self):
        # <mac> - <nasip> - <nasport> - "Cleartext-Password" - := - <mac> - 10
        # We have one interface with a MAC whose room has two ports on the same switch
        rows = session.session.query(hades.radcheck.table).all()
        host = self.user.hosts[0]
        mac = host.interfaces[0].mac
        for row in rows:
            self.assertEqual(row.UserName, mac)
            self.assertEqual(row.NASIPAddress, self.switch.management_ip)
            self.assertEqual(row.Attribute, "User-Name")
            self.assertEqual(row.Op, "=*")
            self.assertEqual(row.Value, None)
            self.assertEqual(row.Priority, 10)

        self.assertEqual({row.NASPortId for row in rows},
                         {port.switch_port.name for port in host.room.patch_ports})

    def test_radgroupcheck(self):
        rows = session.session.query(hades.radgroupcheck.table).all()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row, ("unknown", "Auth-Type", ":=", "Accept", 10))

    # Radreply is empty by default...

    def test_radgroupreply_custom_entries(self):
        radgroupreply_q = session.session.query(hades.radgroupreply.table)
        custom_reply_row = ("TestGroup", "Egress-VLAN-Name", "+=", "2Servernetz")
        self.assertNotIn(custom_reply_row, radgroupreply_q.all())
        session.session.execute(hades.radgroupreply_base.insert([custom_reply_row]))
        session.session.commit()
        self.assertIn(custom_reply_row, radgroupreply_q.all())

    def test_radgroupreply_access_groups(self):
        rows = session.session.query(hades.radgroupreply.table).all()
        vlans = VLAN.q.all()
        for vlan in vlans:
            with self.subTest(vlan=vlan):
                group_name = "{}_untagged".format(vlan.name)
                self.assertIn((group_name, "Egress-VLAN-Name", "+=", "2{}".format(vlan.name)), rows)
                self.assertIn((group_name, "Fall-Through", ":=", "Yes"), rows)

                group_name = "{}_tagged".format(vlan.name)
                self.assertIn((group_name, "Egress-VLAN-Name", "+=", "1{}".format(vlan.name)), rows)
                self.assertIn((group_name, "Fall-Through", ":=", "Yes"), rows)

    def test_radgroupreply_blocking_groups(self):
        props = [x[0] for x in session.session.query(hades.radius_property).all()]
        rows = session.session.query(hades.radgroupreply.table).all()
        for prop in props:
            self.assertIn((prop, "Egress-VLAN-Name", ":=", "2hades-unauth"), rows)
            self.assertIn((prop, "Fall-Through", ":=", "No"), rows)

    def test_radusergroup_access(self):
        host = self.user.hosts[0]
        switch_ports = [p.switch_port for p in host.room.connected_patch_ports]
        self.assertEqual(len(host.ips), 1)
        self.assertEqual(len(host.interfaces), 1)
        mac = host.interfaces[0].mac
        group = "{}_untagged".format(host.ips[0].subnet.vlan.name)

        rows = session.session.query(hades.radusergroup.table).all()
        for switch_port in switch_ports:
            self.assertIn((mac, switch_port.switch.management_ip, switch_port.name, group, 20),
                          rows)

    def test_dhcphost_access(self):
        rows = session.session.query(hades.dhcphost.table).all()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        host = self.user.hosts[0]
        self.assertEqual(row, (host.interfaces[0].mac, str(host.ips[0].address)))

    def test_alternative_dns(self):
        # Nobody is cache user by default
        self.assertEqual(session.session.query(hades.alternative_dns.table).count(), 0)
        # add cache group
        cache_group = PropertyGroupFactory.create(name="Cache User",
                                                  granted={'cache_access'})

        MembershipFactory.create(user=self.user, group=cache_group,
                                 begins_at=datetime.now() + timedelta(-1),
                                 ends_at=datetime.now() + timedelta(1))
        rows = session.session.query(hades.alternative_dns.table).all()
        ip = self.user.hosts[0].ips[0]
        self.assertEqual(rows, [(str(ip.address),)])


class HadesBlockedViewTest(HadesTestBase):
    def create_factories(self):
        super().create_factories()
        MembershipFactory.create(user=self.user, group=self.payment_in_default_group,
                                 begins_at=datetime.now() + timedelta(-1),
                                 ends_at=datetime.now() + timedelta(1))

    def test_radusergroup_blocked(self):
        host = self.user.hosts[0]
        switch_ports = [p.switch_port for p in host.room.connected_patch_ports]
        self.assertEqual(len(host.ips), 1)
        self.assertEqual(len(host.interfaces), 1)
        mac = host.interfaces[0].mac

        rows = session.session.query(hades.radusergroup.table).all()
        for switch_port in switch_ports:
            self.assertIn((mac, switch_port.switch.management_ip, switch_port.name,
                           'payment_in_default', -10),
                          rows)
            self.assertIn((mac, switch_port.switch.management_ip, switch_port.name,
                           'no_network_access', 0),
                          rows)

    def test_dhcphost_blocked(self):
        rows = session.session.query(hades.dhcphost.table).all()
        self.assertEqual(len(rows), 0)

    def test_no_alternative_dns(self):
        cache_group = PropertyGroupFactory.create(name="Cache User",
                                                  granted={'cache_access'})

        MembershipFactory.create(user=self.user, group=cache_group,
                                 begins_at=datetime.now() + timedelta(-1),
                                 ends_at=datetime.now() + timedelta(1))
        self.assertEqual(session.session.query(hades.alternative_dns.table).count(), 0)
