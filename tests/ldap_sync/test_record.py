from unittest import TestCase

from pycroft.ldap_sync.record import Record, RecordState, _canonicalize_to_list
from pycroft.ldap_sync.action import AddAction, DeleteAction, IdleAction, ModifyAction


class RecordTestCase(TestCase):
    def setUp(self):
        self.record = Record(dn='test', attrs={'bar': 'shizzle'})

    def test_record_equality(self):
        self.assertEqual(self.record, Record(dn='test', attrs={'bar': 'shizzle'}))

    def test_record_noncanonical_equality(self):
        self.assertEqual(self.record, Record(dn='test', attrs={'bar': ['shizzle']}))

    def test_record_subtraction_with_none_adds(self):
        difference = self.record - None
        self.assertIsInstance(difference, AddAction)
        self.assertEqual(difference.record, self.record)

    def test_none_subtracted_by_record_deletes(self):
        difference = None - self.record
        self.assertIsInstance(difference, DeleteAction)
        self.assertEqual(difference.record, self.record)

    def test_different_dn_raises_typeerror(self):
        with self.assertRaises(TypeError):
            # pylint: disable=expression-not-assigned
            self.record - Record(dn='notatest', attrs={})

    def test_same_record_subtraction_idles(self):
        difference = self.record - self.record
        self.assertIsInstance(difference, IdleAction)

    def test_correctly_different_record_modifies(self):
        difference = self.record - Record(dn='test', attrs={'bar': ''})
        self.assertIsInstance(difference, ModifyAction)

    def test_record_from_ldap_record(self):
        ldapsearch_record = {'dn': 'somedn',
                             'attributes': {'foo': u'bar', 'shizzle': u'baz'},
                             'raw_attributes': {'foo': b'bar'}}
        record = Record.from_ldap_record(ldapsearch_record)
        self.assertEqual(record.attrs, {'foo': [u'bar'], 'shizzle': [u'baz']})


class EmptyAttributeRecordTestCase(TestCase):
    def setUp(self):
        self.record = Record(dn='test', attrs={'emailAddress': None})

    def test_attribute_is_empty_list(self):
        self.assertEqual(self.record.attrs['emailAddress'], [])

    def test_empty_attribute_removed(self):
        self.record.remove_empty_attributes()
        self.assertNotIn('emailAddress', self.record.attrs)


class RecordFromOrmTestCase(TestCase):
    class complete_user(object):
        name = 'foo bar shizzle'
        login = 'shizzle'
        email = 'shizzle@agdsn.de'
        class unix_account(object):
            uid = 10006
            gid = 100
            home_directory = '/home/test'
            login_shell = '/bin/bash'
        passwd_hash = 'somehash'

    def setUp(self):
        self.attrs = Record.from_db_user(self.complete_user, base_dn='o=test').attrs

    def test_attributes_passed(self):
        pass

    def test_uid_correct(self):
        self.assertEqual(self.attrs['uid'], ['shizzle'])

    def test_uidNumber_correct(self):
        self.assertEqual(self.attrs['uidNumber'], [10006])

    def test_gidNumber_correct(self):
        self.assertEqual(self.attrs['gidNumber'], [100])

    def test_homeDirectory_correct(self):
        self.assertEqual(self.attrs['homeDirectory'], ['/home/test'])

    def test_userPassword_correct(self):
        self.assertEqual(self.attrs['userPassword'], ['somehash'])

    def test_gecos_correct(self):
        self.assertEqual(self.attrs['gecos'], ['foo bar shizzle'])

    def test_cn_correct(self):
        self.assertEqual(self.attrs['cn'], ['foo bar shizzle'])

    def test_sn_correct(self):
        self.assertEqual(self.attrs['sn'], ['foo bar shizzle'])

    def test_emailAddress_correct(self):
        self.assertEqual(self.attrs['emailAddress'], ['shizzle@agdsn.de'])


class CanonicalizationTestCase(TestCase):
    def test_empty_string_gives_empty_list(self):
        self.assertEqual(_canonicalize_to_list(''), [])

    def test_none_gives_empty_list(self):
        self.assertEqual(_canonicalize_to_list(None), [])

    def test_zero_gets_kept(self):
        self.assertEqual(_canonicalize_to_list(0), [0])

    def test_string_gets_kept(self):
        self.assertEqual(_canonicalize_to_list('teststring'), ['teststring'])

    def test_false_gets_kept(self):
        self.assertEqual(_canonicalize_to_list(False), [False])

    def test_empty_list_gets_passed_identially(self):
        self.assertEqual(_canonicalize_to_list([]), [])

    def test_filled_list_gets_passed_identially(self):
        self.assertEqual(_canonicalize_to_list(['l', 'bar', 0, None]), ['l', 'bar', 0, None])


class RecordStateTestCase(TestCase):
    def setUp(self):
        self.record = Record(dn='test', attrs={})

    def test_equality_both_none(self):
        self.assertEqual(RecordState(), RecordState())

    def test_equality_only_current(self):
        self.assertEqual(RecordState(current=self.record), RecordState(current=self.record))

    def test_equality_only_desired(self):
        self.assertEqual(RecordState(desired=self.record), RecordState(desired=self.record))

    def test_equality_current_and_desired(self):
        self.assertEqual(RecordState(current=self.record, desired=self.record),
                         RecordState(current=self.record, desired=self.record))

    def test_not_equal_to_none(self):
        self.assertNotEqual(RecordState(), RecordState(current=self.record))