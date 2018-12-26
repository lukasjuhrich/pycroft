from flask import url_for
from flask_login import current_user
from wtforms.widgets.core import html_params

from web.blueprints.helpers.table import BootstrapTable, Column, BtnColumn, \
    LinkColumn


class RefreshableTableMixin:
    """A mixin class showing the refresh button by default.

    In :py:meth:`__init__`s ``table_args`` argument, a default of
    ``{'data-show-refresh': "true"}`` is established.
    """
    def __init__(self, *a, **kw):
        table_args = kw.pop('table_args', {})
        table_args.setdefault('data-show-refresh', "true")
        kw['table_args'] = table_args
        super().__init__(*a, **kw)


class LogTableExtended(RefreshableTableMixin, BootstrapTable):
    """A table for displaying logs, with a ``type`` column"""
    created_at = Column("Erstellt um", formatter='table.dateFormatter', width=2)
    type_ = Column("Logtyp", name='type')
    user = Column("Nutzer", formatter='table.userFormatter')
    message = Column("Nachricht")


class LogTableSpecific(RefreshableTableMixin, BootstrapTable):
    """A table for displaying logs"""
    created_at = Column("Erstellt um", formatter='table.dateFormatter', width=2)
    user = Column("Nutzer", formatter='table.userFormatter')
    message = Column("Nachricht")


class MembershipTable(BootstrapTable):
    """A table for displaying memberships

    In the toolbar, a “new membership” button is inserted if the
    :py:obj:`current_user` has the ``add_membership`` property.
    """
    group_name = Column("Gruppe")
    begins_at = Column("Beginn", formatter='table.dateFormatter')
    ends_at = Column("Ende", formatter='table.dateFormatter')
    actions = Column("Aktionen", formatter='table.multiBtnFormatter')

    def __init__(self, *a, user_id=None, **kw):
        super().__init__(*a, **kw)
        self.user_id = user_id

    def generate_toolbar(self):
        if self.user_id is None:
            return
        if not current_user.has_property('groups_change_membership'):
            return
        args = {
            'class': "btn btn-primary",
            'href': url_for(".add_membership", user_id=self.user_id),
        }
        yield "<a {}>".format(html_params(**args))
        yield "<span class=\"glyphicon glyphicon-plus\"></span>"
        yield "Mitgliedschaft"
        yield "</a>"


class HostTable(BootstrapTable):
    """A table for displaying hosts
    """
    name = Column("Name")
    switch = Column("Switch")
    port = Column("SwitchPort")
    edit_link = BtnColumn("Editieren")
    delete_link = BtnColumn("Löschen")

    def __init__(self, *a, user_id=None, **kw):
        super().__init__(*a, **kw)
        self.user_id = user_id

    def generate_toolbar(self):
        if self.user_id is None:
            return
        if not current_user.has_property('user_hosts_change'):
            return
        args = {
            'class': "btn btn-primary",
            'href': url_for(".host_create", user_id=self.user_id),
        }
        yield "<a {}>".format(html_params(**args))
        yield "<span class=\"glyphicon glyphicon-plus\"></span>"
        yield "Host"
        yield "</a>"


class InterfaceTable(BootstrapTable):
    """A table for displaying interfaces
    """
    host = Column("Host")
    mac = Column("MAC")
    ips = Column("IPs")
    edit_link = BtnColumn("Editieren")
    delete_link = BtnColumn("Löschen")

    def __init__(self, *a, user_id=None, **kw):
        super().__init__(*a, **kw)
        self.user_id = user_id

    def generate_toolbar(self):
        if self.user_id is None:
            return
        if not current_user.has_property('user_hosts_change'):
            return
        args = {
            'class': "btn btn-primary",
            'href': url_for(".interface_create", user_id=self.user_id),
        }
        yield "<a {}>".format(html_params(**args))
        yield "<span class=\"glyphicon glyphicon-plus\"></span>"
        yield "Interface"
        yield "</a>"


class SearchTable(BootstrapTable):
    """A table for displaying search results"""
    id = Column("ID")
    url = LinkColumn("Name")
    login = Column("Login")
