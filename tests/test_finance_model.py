# Copyright (c) 2012 The Pycroft Authors. See the AUTHORS file.
# This file is part of the Pycroft project and licensed under the terms of
# the Apache License, Version 2.0. See the LICENSE file for details.
import unittest

from pycroft import model
from pycroft.model import session, user, finance, _all


class Test_010_TransactionSplits(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        session.reinit_session("sqlite://")
        model.drop_db_model()
        model.create_db_model()
        cls.account = finance.FinanceAccount(name="Testaccount", type="EXPENSE")
        cls.s = session.session
        cls.s.add(cls.account)
        cls.s.commit()

    def tearDown(self):
        super(Test_010_TransactionSplits, self).tearDown()
        print "bla"
        self.s.remove()

    def test_0010_empty_transaction(self):
        tr = finance.Transaction(message="Transaction1")
        self.s.add(tr)
        self.s.commit()
        self.assertEqual(finance.Transaction.q.filter_by(message="Transaction1").count(), 1)

    def test_0020_fail_on_unbalanced(self):
        tr = finance.Transaction(message="Transaction2")
        self.s.add(tr)
        self.s.commit()
        sp1 = finance.Split(amount=100, account=self.account, transaction=tr)
        self.s.add(sp1)
        self.assertRaisesRegexp(Exception, 'Transaction "Transaction2" is not balanced!', self.s.commit)
        #self.s.rollback()

    def test_0030_insert_balanced(self):
        tr = finance.Transaction(message="Transaction2")
        self.s.add(tr)
        self.s.commit()
        sp1 = finance.Split(amount=100, account=self.account, transaction=tr)
        sp2 = finance.Split(amount=-100, account=self.account, transaction=tr)
        self.s.add(sp1)
        self.s.add(sp2)
        self.s.commit()
