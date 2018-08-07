# -*- coding: utf-8 -*-
# Copyright (c) 2016 The Pycroft Authors. See the AUTHORS file.
# This file is part of the Pycroft project and licensed under the terms of
# the Apache License, Version 2.0. See the LICENSE file for details.
from abc import ABCMeta, abstractmethod
from collections import namedtuple
import csv
from datetime import datetime, date, timedelta
from decimal import Decimal
import difflib
from functools import partial
from itertools import chain, islice, starmap, tee, zip_longest
from io import StringIO
import operator
import re

from sqlalchemy import or_, and_, literal_column, literal, select, exists, not_
from sqlalchemy.orm import aliased
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy import func, between, Integer, cast

from pycroft import config, model
from pycroft.helpers.i18n import deferred_gettext, gettext, Message
from pycroft.lib.logging import log_user_event
from pycroft.lib.membership import make_member_of, remove_member_of
from pycroft.model import session
from pycroft.model.finance import (
    Account, BankAccount, BankAccountActivity, Split, Transaction, MembershipFee)
from pycroft.helpers.interval import (
    closed, single, Bound, Interval, IntervalSet, UnboundedInterval, closedopen,
    PositiveInfinity)
from pycroft.model.functions import sign, least
from pycroft.model.property import CurrentProperty
from pycroft.model.session import with_transaction
from pycroft.model.types import Money
from pycroft.model.user import User, Membership, PropertyGroup


def get_membership_fees(interval_set=None):
    """

    :param when:
    :return:
    """

    queries = []

    if interval_set is not None:
        for interval in interval_set:
            criteria = []

            if interval.begin is not None:
                if not interval.end == PositiveInfinity:
                    criteria.append(or_(
                        interval.begin <= model.finance.MembershipFee.begins_on,
                        between(interval.begin,
                                model.finance.MembershipFee.begins_on,
                                model.finance.MembershipFee.ends_on)
                    ))

            if interval.end is not None:
                if interval.end == PositiveInfinity:
                    criteria.append(
                        interval.end > model.finance.MembershipFee.begins_on
                    )
                else:
                    criteria.append(or_(
                        interval.end >= model.finance.MembershipFee.ends_on,
                        between(interval.end,
                                model.finance.MembershipFee.begins_on,
                                model.finance.MembershipFee.ends_on)
                    ))


            queries.append(model.finance.MembershipFee.q.filter(or_(*criteria)) \
                           .order_by(model.finance.MembershipFee.begins_on))

    if len(queries) >= 1:
        result = queries[0]

        queries.pop(0)

        result.union(*tuple(queries))

        return result.all()
    else:
        return []


def get_membership_fee_for_date(target_date):
    """
    Get the membership fee which contains a given target date.
    :param date target_date: The date for which a corresponding membership
    fee should be found.
    :rtype: MembershipFee
    :raises sqlalchemy.orm.exc.NoResultFound if no membership fee was found
    :raises sqlalchemy.orm.exc.MultipleResultsFound if multiple membership fees
    were found.
    """
    return model.finance.MembershipFee.q.filter(
        between(target_date, model.finance.MembershipFee.begins_on,
                model.finance.MembershipFee.ends_on)
    ).one()


def get_last_applied_membership_fee():
    """
    Get the last applied membership fee.
    :rtype: MembershipFee
    """
    return model.finance.MembershipFee.q.filter(
        model.finance.MembershipFee.ends_on <= datetime.now()) \
        .order_by(model.finance.MembershipFee.ends_on.desc()).first()


def get_first_applied_membership_fee():
    """
    Get the first applied membership fee.
    :rtype: MembershipFee
    """
    return model.finance.MembershipFee.q.order_by(
        model.finance.MembershipFee.ends_on.desc()).first()


@with_transaction
def simple_transaction(description, debit_account, credit_account, amount,
                       author, valid_on=None):
    """
    Posts a simple transaction.
    A simple transaction is a transaction that consists of exactly two splits,
    where one account is debited and another different account is credited with
    the same amount.
    The current system date will be used as transaction date, an optional valid
    date may be specified.
    :param unicode description: Description
    :param Account debit_account: Debit (germ. Soll) account.
    :param Account credit_account: Credit (germ. Haben) account
    :param Decimal amount: Amount in Eurocents
    :param User author: User who created the transaction
    :param date valid_on: Date, when the transaction should be valid. Current
    database date, if omitted.
    :type valid_on: date or None
    :rtype: Transaction
    """
    if valid_on is None:
        valid_on = session.utcnow().date()
    new_transaction = Transaction(
        description=description,
        author=author,
        valid_on=valid_on)
    new_debit_split = Split(
        amount=-amount,
        account=debit_account,
        transaction=new_transaction)
    new_credit_split = Split(
        amount=amount,
        account=credit_account,
        transaction=new_transaction)
    session.session.add_all(
        [new_transaction, new_debit_split, new_credit_split]
    )
    return new_transaction


@with_transaction
def complex_transaction(description, author, splits, valid_on=None):
    if valid_on is None:
        valid_on = session.utcnow().date()
    objects = []
    new_transaction = Transaction(
        description=description,
        author=author,
        valid_on=valid_on
    )
    objects.append(new_transaction)
    objects.extend(
        Split(amount=amount, account=account, transaction=new_transaction)
        for (account, amount) in splits
    )
    session.session.add_all(objects)
    return new_transaction


def transferred_amount(from_account, to_account, when=UnboundedInterval):
    """
    Determine how much has been transferred from one account to another in a
    given interval.

    A negative value indicates that more has been transferred from to_account
    to from_account than the other way round.

    The interval boundaries may be None, which indicates no lower and upper
    bound respectively.
    :param Account from_account: source account
    :param Account to_account: destination account
    :param Interval[date] when: Interval in which transactions became valid
    :rtype: int
    """
    split1 = aliased(Split)
    split2 = aliased(Split)
    query = session.session.query(
        cast(func.sum(
            sign(split2.amount) *
            least(func.abs(split1.amount), func.abs(split2.amount))
        ), Money)
    ).select_from(
        split1
    ).join(
        (split2, split1.transaction_id == split2.transaction_id)
    ).join(
        Transaction, split2.transaction_id == Transaction.id
    ).filter(
        split1.account == from_account,
        split2.account == to_account,
        sign(split1.amount) != sign(split2.amount)
    )
    if not when.unbounded:
        query = query.filter(
            between(Transaction.valid_on, when.begin, when.end)
        )
    elif when.begin is not None:
        query = query.filter(Transaction.valid_on >= when.begin)
    elif when.end is not None:
        query = query.filter(Transaction.valid_on <= when.end)
    return query.scalar()


adjustment_description = deferred_gettext(
    u"Korrektur von „{original_description}“ vom {original_valid_on}")


@with_transaction
def post_transactions_for_membership_fee(membership_fee, processor):
    """
    Posts transactions (and splits) for users where the specified membership fee
    was not posted yet.

    User select: User -> Split (user account) -> Transaction -> Split (fee account)
                 Conditions: User has `membership_fee` property on
                             begins_on + 1 day and begins_on + grace - 1 day

    :param membership_fee: The membership fee which should be posted
    :param processor:
    :return: A list of name of all affected users
    """

    description = MembershipFee.description.format(
        fee_name=membership_fee.name).to_json()

    split_user_account = Split.__table__.alias()
    split_fee_account = Split.__table__.alias()

    users = (select([User.id.label('user_id'), User.name.label('user_name'), User.account_id.label('account_id')])
            .select_from(User.__table__
                .join(func.evaluate_properties(membership_fee.begins_on + timedelta(1))
                .alias('properties_beginning'), literal_column('properties_beginning.user_id') == User.id)
                .join(func.evaluate_properties(membership_fee.begins_on + membership_fee.grace_period - timedelta(1))
                .alias('properties_grace'), literal_column('properties_grace.user_id') == User.id)
            )
            .where(not_(exists(select([None]).select_from(split_user_account
                    .join(Transaction, Transaction.id == split_user_account.c.transaction_id)
                    .join(split_fee_account, split_fee_account.c.transaction_id == Transaction.id)
                )
                .where(and_(split_user_account.c.account_id == User.account_id,
                            Transaction.valid_on.between(literal(membership_fee.begins_on), literal(membership_fee.ends_on)),
                            split_fee_account.c.account_id == literal(config.membership_fee_account_id),
                            split_fee_account.c.id != split_user_account.c.id))
            )))
            .where(or_(literal_column('properties_beginning.property_name') == 'membership_fee',
                        literal_column('properties_grace.property_name') == 'membership_fee'))
            .distinct()
            .cte('membership_fee_users'))

    numbered_users = (select([users.c.user_id, users.c.account_id, func.row_number().over().label('index')])
                      .select_from(users)
                      .cte("membership_fee_numbered_users"))

    transactions = (Transaction.__table__.insert()
         .from_select([Transaction.description, Transaction.author_id, Transaction.posted_at, Transaction.valid_on],
                      select([literal(description), literal(processor.id), literal(datetime.utcnow()), literal(membership_fee.ends_on)]).select_from(users))
         .returning(Transaction.id)
         .cte('membership_fee_transactions'))

    numbered_transactions = (select([transactions.c.id, func.row_number().over().label('index')])
         .select_from(transactions)
         .cte('membership_fee_numbered_transactions'))

    split_insert_fee_account = (Split.__table__.insert()
        .from_select([Split.amount, Split.account_id, Split.transaction_id],
                     select([literal(-membership_fee.regular_fee, type_=Money), literal(config.membership_fee_account_id),transactions.c.id])
                     .select_from(transactions))
        .returning(Split.id)
        .cte('membership_fee_split_fee_account'))

    split_insert_user = (Split.__table__.insert().from_select(
        [Split.amount, Split.account_id, Split.transaction_id],
        select([literal(membership_fee.regular_fee, type_=Money), numbered_users.c.account_id, numbered_transactions.c.id])
        .select_from(numbered_users.join(numbered_transactions,
                    numbered_transactions.c.index == numbered_users.c.index)))
        .returning(Split.id)
        .cte('membership_fee_split_user'))

    affected_users_raw = session.session.execute(select([users.c.user_id, users.c.user_name])).fetchall()

    # TODO: Unite the following two queries into one (the membership_fee_users is called twice currently.
    session.session.execute(select([]).select_from(split_insert_fee_account
                                       .join(split_insert_user, split_insert_user.c.id == split_insert_fee_account.c.id)))

    affected_users = []

    for user in affected_users_raw:
        affected_users.insert(0, {'id': user[0], 'name': user[1]})

    return affected_users


def post_fees(users, fees, processor):
    """
    Calculate the given fees for all given user accounts from scratch and post
    them if they have not already been posted and correct erroneous postings.
    :param iterable[User] users:
    :param iterable[Fee] fees:
    :param User processor:
    """

    new_transactions = []

    for user in users:
        for fee in fees:
            computed_debts = fee.compute(user)

            try:
                posted_transactions = fee.get_posted_transactions(user).all()
            except AttributeError:
                continue

            posted_credits = tuple(
                t for t in posted_transactions if t.amount > 0)

            posted_corrections = tuple(
               t for t in posted_transactions if t.amount < 0)

            missing_debts, erroneous_debts = diff(posted_credits,
                                                  computed_debts)

            computed_adjustments = tuple(
                ((adjustment_description.format(
                    original_description=Message.from_json(description).localize(),
                    original_valid_on=valid_on)).to_json(),
                 valid_on, -amount)
                for description, valid_on, amount in erroneous_debts)
            missing_adjustments, erroneous_adjustments = diff(
                posted_corrections, computed_adjustments
            )
            missing_postings = chain(missing_debts, missing_adjustments)

            today = session.utcnow().date()
            for description, valid_on, amount in missing_postings:
                if valid_on <= today:
                    simple_transaction(
                        description, fee.account, user.account,
                        amount, processor, valid_on)

                    new_transactions.append({
                        'user_id': user.id,
                        'description': description,
                        'amount': amount,
                        'valid_on': valid_on
                    })

    return new_transactions


def diff(posted, computed, insert_only=False):
    sequence_matcher = difflib.SequenceMatcher(None, posted, computed)
    missing_postings = []
    erroneous_postings = []
    for tag, i1, i2, j1, j2 in sequence_matcher.get_opcodes():
        if 'replace' == tag:
            if insert_only:
                continue

            erroneous_postings.extend(islice(posted, i1, i2))
            missing_postings.extend(islice(computed, j1, j2))
        if 'delete' == tag:
            if insert_only:
                continue

            erroneous_postings.extend(islice(posted, i1, i2))
        if 'insert' == tag:
            missing_postings.extend(islice(computed, j1, j2))
    return missing_postings, erroneous_postings


def _to_date_interval(interval):
    """
    :param Interval[datetime] interval:
    :rtype: Interval[date]
    """
    if interval.lower_bound.unbounded:
        lower_bound = interval.lower_bound
    else:
        lower_bound = Bound(interval.lower_bound.value.date(),
                            interval.lower_bound.closed)
    if interval.upper_bound.unbounded:
        upper_bound = interval.upper_bound
    else:
        upper_bound = Bound(interval.upper_bound.value.date(),
                            interval.upper_bound.closed)
    return Interval(lower_bound, upper_bound)


def _to_date_intervals(intervals):
    """
    :param IntervalSet[datetime] intervals:
    :rtype: IntervalSet[date]
    """
    return IntervalSet(_to_date_interval(i) for i in intervals)


class Fee(metaclass=ABCMeta):
    """
    Fees must be idempotent, that means if a fee has been applied to a user,
    another application must not result in any change. This property allows
    all the fee to be calculated for all times instead of just the current
    semester or the current day and makes the calculation independent of system
    time it was running.
    """

    validity_period = UnboundedInterval

    def __init__(self, account):
        self.account = account
        self.session = session.session

    def get_posted_transactions(self, user):
        """
        Get all fee transactions that have already been posted to the user's
        finance account.
        :param User user:
        :return:
        :rtype: list[(unicode, date, int)]
        """

        first_fee = get_first_applied_membership_fee()

        if first_fee is None:
            return []

        split1 = aliased(Split)
        split2 = aliased(Split)
        transactions = self.session.query(
            Transaction.description, Transaction.valid_on, split1.amount
        ).select_from(Transaction).join(
            (split1, split1.transaction_id == Transaction.id),
            (split2, split2.transaction_id == Transaction.id)
        ).filter(
            split1.account_id == user.account_id,
            split2.account_id == self.account.id
        ).filter(
            Transaction.valid_on >= first_fee.ends_on
        ).order_by(Transaction.valid_on)

        return transactions

    @abstractmethod
    def compute(self, user):
        """
        Compute all debts the user owes us for this particular fee. Debts must
        be in ascending order of valid_on.

        :param User user:
        :rtype: list[(unicode, date, int)]
        """
        pass


class RegistrationFee(Fee):
    description = deferred_gettext(u"Anschlussgebühr").to_json()

    def compute(self, user):
        when = single(user.registered_at)
        if user.has_property("registration_fee", when):
            try:
                mfee = get_membership_fee_for_date(
                    user.registered_at.date())
            except NoResultFound:
                return []
            fee = mfee.registration_fee
            if fee > 0:
                return [(self.description, user.registered_at.date(), fee)]
        return []


class MembershipFee(Fee):
    description = deferred_gettext(
        u"Mitgliedsbeitrag {fee_name}")

    def compute(self, user):
        regular_fee_intervals = _to_date_intervals(
            user.property_intervals("membership_fee"))

        reduced_fee_intervals = _to_date_intervals(
            user.property_intervals("reduced_membership_fee"))

        debts = []

        fee_intervals = regular_fee_intervals | reduced_fee_intervals

        # Compute membership fee for each period the user is liable to pay it
        membership_fees = get_membership_fees(fee_intervals)
        for membership_fee in membership_fees:
            if membership_fee.ends_on > date.today():
                continue

            fee_interval = closed(membership_fee.begins_on,
                                  membership_fee.ends_on)
            reg_fee_in_period = regular_fee_intervals & fee_interval
            red_fee_in_period = reduced_fee_intervals & fee_interval

            # reduced fee trumps regular fee
            reg_fee_in_period = reg_fee_in_period - red_fee_in_period

            valid_on = membership_fee.ends_on

            fee_in_period = reg_fee_in_period | red_fee_in_period

            first_fee = False

            for regular_fee_interval in regular_fee_intervals:
                if regular_fee_interval.begin.month == membership_fee.begins_on.month:
                    first_fee = True

            # IntervalSet is type-agnostic, so cannot do .length of empty sets,
            # therefore these double checks are required
            if (reg_fee_in_period and
                    (not red_fee_in_period or red_fee_in_period.length <
                     membership_fee.reduced_fee_threshold) and
                    (fee_in_period.length > membership_fee.grace_period or
                     not first_fee)):
                amount = membership_fee.regular_fee
            elif (red_fee_in_period and
                  fee_in_period.length > membership_fee.grace_period and
                  red_fee_in_period.length >=
                  membership_fee.reduced_fee_threshold):
                amount = membership_fee.reduced_fee
            else:
                continue

            if amount > 0:
                debts.append((self.description.format(
                                fee_name=membership_fee.name).to_json(),
                              valid_on, amount))
        return debts


class LateFee(Fee):
    description = deferred_gettext(
        u"Versäumnisgebühr für Beitrag vom {original_valid_on}")

    def __init__(self, account, calculate_until):
        """
        :param date calculate_until: Date up until late fees are calculated;
        usually the date of the last bank import
        :param int allowed_overdraft: Amount of overdraft which does result
        in an late fee being charged.
        :param payment_deadline: Timedelta after which a payment is late
        """
        super(LateFee, self).__init__(account)
        self.calculate_until = calculate_until

    def non_late_fee_transactions(self, user):
        split1 = aliased(Split)
        split2 = aliased(Split)
        return self.session.query(
            Transaction.valid_on, (-func.sum(split2.amount)).label("debt")
        ).select_from(Transaction).join(
            (split1, split1.transaction_id == Transaction.id),
            (split2, split2.transaction_id == Transaction.id)
        ).filter(
            split1.account_id == user.account_id,
            split2.account_id != user.account_id,
            split2.account_id != self.account.id
        ).group_by(
            Transaction.id, Transaction.valid_on
        ).order_by(Transaction.valid_on)

    @staticmethod
    def running_totals(transactions):
        balance = 0
        last_credit = transactions[0][0]
        for valid_on, amount in transactions:
            if amount > 0:
                last_credit = valid_on
            else:
                delta = valid_on - last_credit
                yield last_credit, balance, delta
            balance += amount

    def compute(self, user):
        # Note: User finance accounts are assets accounts from our perspective,
        # that means their balance is positive, if the user owes us money
        transactions = self.non_late_fee_transactions(user).all()
        # Add a pseudo transaction on the day until late fees should be
        # calculated
        transactions.append((self.calculate_until, 0))
        liability_intervals = _to_date_intervals(
            user.property_intervals("late_fee")
        )
        debts = []
        for last_credit, balance, delta in self.running_totals(transactions):
            try:
                membership_fee = get_membership_fee_for_date(last_credit)

                if membership_fee.late_fee > 0:
                    if (
                            balance < membership_fee.not_allowed_overdraft_late_fee or
                            delta <= membership_fee.payment_deadline):
                        continue
                    valid_on = last_credit + membership_fee.payment_deadline + timedelta(
                        days=1)
                    amount = membership_fee.late_fee
                    if liability_intervals & single(valid_on) and amount > 0:
                        debts.append((
                            self.description.format(
                                original_valid_on=last_credit).to_json(),
                            amount, valid_on
                        ))
            except NoResultFound:
                pass
        return debts


MT940_FIELDNAMES = [
    'our_account_number',
    'posted_on',
    'valid_on',
    'type',
    'reference',
    'other_name',
    'other_account_number',
    'other_routing_number',
    'amount',
    'currency',
    'info',
]

MT940Record = namedtuple("MT940Record", MT940_FIELDNAMES)


class MT940Dialect(csv.Dialect):
    delimiter = ";"
    quotechar = '"'
    doublequote = True
    skipinitialspace = True
    lineterminator = '\n'
    quoting = csv.QUOTE_ALL


class CSVImportError(Exception):

    def __init__(self, message, cause=None):
        if cause is not None:
            message = gettext(u"{0}\nCaused by:\n{1}").format(
                message, cause
            )
        self.cause = cause
        super(CSVImportError, self).__init__(message)


def is_ordered(iterable, relation=operator.le):
    """
    Check that an iterable is ordered with respect to a given relation.
    :param iterable[T] iterable: an iterable
    :param (T,T) -> bool op: a binary relation (i.e. a function that returns a bool)
    :return: True, if each element and its successor yield True under the given
    relation.
    :rtype: bool
    """
    a, b = tee(iterable)
    try:
        next(b)
    except StopIteration:
        # iterable is empty
        return True
    return all(relation(x, y) for x, y in zip(a, b))


@with_transaction
def import_bank_account_activities_csv(csv_file, expected_balance,
                                       imported_at=None):
    """
    Import bank account activities from a MT940 CSV file into the database.

    The new activities are merged with the activities that are already saved to
    the database.
    :param csv_file:
    :param expected_balance:
    :param imported_at:
    :return:
    """

    if imported_at is None:
        imported_at = session.utcnow()

    # Convert to MT940Record and enumerate
    reader = csv.reader(csv_file, dialect=MT940Dialect)
    records = enumerate((MT940Record._make(r) for r in reader), 1)
    try:
        # Skip first record (header)
        next(records)
        activities = tuple(
            process_record(index, record, imported_at=imported_at)
            for index, record in records)
    except StopIteration:
        raise CSVImportError(gettext(u"No data present."))
    except csv.Error as e:
        raise CSVImportError(gettext(u"Could not read CSV."), e)
    if not activities:
        raise CSVImportError(gettext(u"No data present."))
    if not is_ordered((a[8] for a in activities), operator.ge):
        raise CSVImportError(gettext(
            u"Transaction are not sorted according to transaction date in "
            u"descending order."))
    first_posted_on = activities[-1][8]
    balance = session.session.query(
        func.coalesce(func.sum(BankAccountActivity.amount), 0)
    ).filter(
        BankAccountActivity.posted_on < first_posted_on
    ).scalar()
    a = tuple(session.session.query(
        BankAccountActivity.amount, BankAccountActivity.bank_account_id,
        BankAccountActivity.reference, BankAccountActivity.original_reference,
        BankAccountActivity.other_account_number,
        BankAccountActivity.other_routing_number,
        BankAccountActivity.other_name, BankAccountActivity.imported_at,
        BankAccountActivity.posted_on, BankAccountActivity.valid_on
    ).filter(
        BankAccountActivity.posted_on >= first_posted_on)
    )
    b = tuple(reversed(activities))
    matcher = difflib.SequenceMatcher(a=a, b=b)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if 'equal' == tag:
            continue
        elif 'insert' == tag:
            balance += sum(a[0] for a in islice(activities, j1, j2))
            session.session.add_all(
                BankAccountActivity(
                    amount=e[0], bank_account_id=e[1], reference=e[2],
                    original_reference=e[3], other_account_number=e[4],
                    other_routing_number=e[5], other_name=e[6],
                    imported_at=e[7], posted_on=e[8], valid_on=e[9]
                ) for e in islice(activities, j1, j2)
            )
        elif 'delete' == tag:
            continue
        elif 'replace' == tag:
            raise CSVImportError(
                gettext(u"Import conflict:\n"
                        u"Database bank account activities:\n{0}\n"
                        u"File bank account activities:\n{1}").format(
                    u'\n'.join(str(x) for x in islice(activities, i1, i2)),
                    u'\n'.join(str(x) for x in islice(activities, j1, j2))))
        else:
            raise AssertionError()
    if balance != expected_balance:
        message = gettext(u"Balance after does not equal expected balance: "
                          u"{0} != {1}.")
        raise CSVImportError(message.format(balance, expected_balance))

    end_payment_in_default_memberships()


def remove_space_characters(field):
    """Remove every 28th character if it is a space character."""
    if field is None:
        return None
    return u"".join(c for i, c in enumerate(field) if i % 28 != 27 or c != u' ')


# Banks are using the original reference field to store several subfields with
# SEPA. Subfields start with a four letter tag name and the plus sign, they
# are separated by space characters.
sepa_description_field_tags = (
    u'EREF', u'KREF', u'MREF', u'CRED', u'DEBT', u'SVWZ', u'ABWA', u'ABWE'
)
sepa_description_pattern = re.compile(''.join(chain(
    '^',
    [r'(?:({0}\+.*?)(?: (?!$)|$))?'.format(tag)
     for tag in sepa_description_field_tags],
    '$'
)), re.UNICODE)


def cleanup_description(description):
    match = sepa_description_pattern.match(description)
    if match is None:
        return description
    return u' '.join(remove_space_characters(f) for f in match.groups() if f is not None)


def restore_record(record):
    string_buffer = StringIO()
    csv.DictWriter(
        string_buffer, MT940_FIELDNAMES, dialect=MT940Dialect
    ).writerow(record._asdict())
    restored_record = string_buffer.getvalue()
    string_buffer.close()
    return restored_record


def process_record(index, record, imported_at):
    if record.currency != u"EUR":
        message = gettext(u"Unsupported currency {0}. Record {1}: {2}")
        raw_record = restore_record(record)
        raise CSVImportError(message.format(record.currency, index, raw_record))
    try:
        bank_account = BankAccount.q.filter_by(
            account_number=record.our_account_number
        ).one()
    except NoResultFound as e:
        message = gettext(u"No bank account with account number {0}. "
                          u"Record {1}: {2}")
        raw_record = restore_record(record)
        raise CSVImportError(
            message.format(record.our_account_number, index, raw_record), e)

    try:
        valid_on = datetime.strptime(record.valid_on, u"%d.%m.%y").date()
        posted_on = datetime.strptime(record.posted_on, u"%d.%m.%y").date()
    except ValueError as e:
        message = gettext(u"Illegal date format. Record {1}: {2}")
        raw_record = restore_record(record)
        raise CSVImportError(message.format(index, raw_record), e)

    try:
        amount = Decimal(record.amount.replace(u",", u"."))
    except ValueError as e:
        message = gettext(u"Illegal value format {0}. Record {1}: {2}")
        raw_record = restore_record(record)
        raise CSVImportError(
            message.format(record.amount, index, raw_record), e)

    return (amount, bank_account.id, cleanup_description(record.reference),
            record.reference, record.other_account_number,
            record.other_routing_number, record.other_name, imported_at,
            posted_on, valid_on)


def user_has_paid(user):
    return user.account.balance <= 0


def get_typed_splits(splits):
    splits = sorted(splits, key=lambda s: s.transaction.posted_at, reverse=True)
    return zip_longest(
        (s for s in splits if s.amount >= 0),
        (s for s in splits if s.amount < 0),
    )

def get_transaction_type(transaction):

    credited = [split.account for split in transaction.splits if split.amount>0]
    debited = [split.account for split in transaction.splits if split.amount<0]

    cd_accs = (credited, debited)
    # all involved accounts have the same type:
    if all(all(a.type == accs[0].type for a in accs) for accs in cd_accs)\
            and all(len(accs)>0 for accs in cd_accs):
        return (cd_accs[0][0].type, cd_accs[1][0].type)


@with_transaction
def end_payment_in_default_memberships():
    processor = User.q.get(0)

    users = User.q.join(User.current_properties) \
                .filter(CurrentProperty.property_name == 'payment_in_default') \
                .join(Account).filter(Account.balance <= 0).all()

    for user in users:
        remove_member_of(user, config.payment_in_default_group, processor,
                             closedopen(session.utcnow(), None))

    return users


@with_transaction
def handle_payments_in_default():
    processor = User.q.get(0)

    # Add memberships and end "member" membership if threshold met
    users = User.q.join(User.current_properties)\
                  .filter(CurrentProperty.property_name == 'membership_fee') \
                  .join(Account).filter(Account.balance > 0).all()

    users_pid_membership = []
    users_membership_terminated = []

    for user in users:
        last_pid_membership = Membership.q.filter(Membership.user_id == user.id) \
            .filter(Membership.group_id == config.payment_in_default_group.id) \
            .order_by(Membership.ends_at.desc()) \
            .first()

        if last_pid_membership is not None:
            if last_pid_membership.ends_at is not None and \
               last_pid_membership.ends_at >= datetime.utcnow() - timedelta(days=7):
                continue

        in_default_days = user.account.in_default_days

        try:
            fee = get_membership_fee_for_date(
                date.today() - timedelta(days=in_default_days))
        except NoResultFound:
            fee = get_last_applied_membership_fee()

        if not fee:
            return [], []

        if not user.has_property('payment_in_default'):
            if in_default_days >= fee.payment_deadline.days:
                make_member_of(user, config.payment_in_default_group,
                               processor, closed(session.utcnow(), None))
                users_pid_membership.append(user)

        if in_default_days >= fee.payment_deadline_final.days:
            remove_member_of(user, config.member_group, processor,
                             closedopen(session.utcnow(), None))
            log_user_event("Mitgliedschaftsende wegen Zahlungsrückstand ({})"
                           .format(fee.name),
                           processor, user)
            users_membership_terminated.append(user)

    return users_pid_membership, users_membership_terminated

def process_transactions(bank_account, statement):
    transactions = []  # new transactions which would be imported
    old_transactions = []  # transactions which are already imported

    for transaction in statement:
        iban = transaction.data['applicant_iban'] if \
            transaction.data['applicant_iban'] is not None else ''
        bic = transaction.data['applicant_bin'] if \
            transaction.data['applicant_bin'] is not None else ''
        other_name = transaction.data['applicant_name'] if \
            transaction.data['applicant_name'] is not None else ''
        new_activity = BankAccountActivity(
            bank_account_id=bank_account.id,
            amount=int(transaction.data['amount'].amount * 100),
            reference=transaction.data['purpose'],
            original_reference=transaction.data['purpose'],
            other_account_number=iban,
            other_routing_number=bic,
            other_name=other_name,
            imported_at=datetime.now(),
            posted_on=transaction.data['entry_date'],
            valid_on=transaction.data['date'],
        )
        if BankAccountActivity.q.filter(and_(
                BankAccountActivity.bank_account_id ==
                new_activity.bank_account_id,
                BankAccountActivity.amount == new_activity.amount,
                BankAccountActivity.reference == new_activity.reference,
                BankAccountActivity.other_account_number ==
                new_activity.other_account_number,
                BankAccountActivity.other_routing_number ==
                new_activity.other_routing_number,
                BankAccountActivity.other_name == new_activity.other_name,
                BankAccountActivity.posted_on == new_activity.posted_on,
                BankAccountActivity.valid_on == new_activity.valid_on
        )).first() is None:
            transactions.append(new_activity)
        else:
            old_transactions.append(new_activity)

    return (transactions, old_transactions)
