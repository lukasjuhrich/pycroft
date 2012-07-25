# -*- coding: utf-8 -*-
"""
    web.blueprints.user
    ~~~~~~~~~~~~~~

    This module defines view functions for /user

    :copyright: (c) 2012 by AG DSN.
"""

from flask import Blueprint, render_template, flash, redirect, url_for,\
    request, jsonify, abort
from pycroft.model.dormitory import Dormitory, Room, Subnet, VLan
from pycroft.model.hosts import Host, NetDevice
from pycroft.model.logging import UserLogEntry
from pycroft.model.session import session
from pycroft.model.user import User
from pycroft.model.properties import Membership
from pycroft.model.accounting import TrafficVolume
from pycroft.helpers import user_helper, host_helper
from sqlalchemy.sql.expression import or_
from web.blueprints.navigation import BlueprintNavigation
from web.blueprints.user.forms import UserSearchForm, UserCreateForm,\
    hostCreateForm, userLogEntry, UserAddGroupMembership, UserEditForm
from web.blueprints.access import login_required, BlueprintAccess
from datetime import datetime, timedelta
from flask.ext.login import current_user

bp = Blueprint('user', __name__, )
nav = BlueprintNavigation(bp, "Nutzer")
access = BlueprintAccess(bp)


@bp.route('/')
@nav.navigate(u"Übersicht")
def overview():
    return redirect(url_for("dormitories.overview"))


@bp.route('/show/<user_id>', methods=['GET', 'POST'])
@access.login_required
def user_show(user_id):
    user = User.q.get(user_id)
    room = Room.q.get(user.room_id)
    form = userLogEntry()

    if form.validate_on_submit():
        newUserLogEntry = UserLogEntry(message=form.message.data,
            timestamp=datetime.now(),
            author_id=current_user.id, user_id=user_id)
        session.add(newUserLogEntry)
        session.commit()
        flash(u'Kommentar hinzugefügt', 'success')

    user_log_list = user.user_log_entries[::-1]

    memberships = Membership.q.filter(Membership.user_id == user.id)
    memberships_active = memberships.filter(
        # it is important to use == here, "is" does not work
        or_(Membership.start_date == None,
            Membership.start_date <= datetime.now())
    ).filter(
        or_(Membership.end_date == None,
            Membership.end_date > datetime.now())
    )

    return render_template('user/user_show.html',
        page_title=u"Nutzer anzeigen",
        user=user, user_logs=user_log_list, room=room, form=form,
        memberships=memberships.all(),
        memberships_active=memberships_active.all())


@bp.route('/add_membership/<int:user_id>/', methods=['GET', 'Post'])
def add_membership(user_id):
    user = User.q.get(user_id)
    if user is None:
        abort(404)
    form = UserAddGroupMembership()
    if form.validate_on_submit():
        newMembership = Membership(user=user, group=form.group_id.data,
            start_date=form.begin_date.data, end_date=form.end_date.data)
        newUserLogEntry = UserLogEntry(author_id=current_user.id,
            message=u"hat Nutzer zur Gruppe '%s' hinzugefügt." %
                    form.group_id.data.name,
            timestamp=datetime.now(), user_id=user_id)

        session.add(newMembership)
        session.add(newUserLogEntry)
        session.commit()
        flash(u'Nutzer wurde der Gruppe hinzugefügt.', 'success')

        return redirect(url_for(".user_show", user_id=user_id))

    return render_template('user/add_membership.html',
        page_title=u"Neue Gruppenmitgliedschaft für Nutzer %s" % user_id,
        user_id=user_id, form=form)


@bp.route('/delete_membership/<int:membership_id>')
def end_membership(membership_id):
    membership = Membership.q.get(membership_id)
    membership.disable()

    # ToDo: Make the log messages not Frontend specific (a helper?)
    newUserLogEntry = UserLogEntry(author_id=current_user.id,
        message=u"hat die Mitgliedschaft des Nutzers"
                u" in der Gruppe '%s' beendet." %
                membership.group.name,
        timestamp=datetime.now(), user_id=membership.user_id)

    session.add(newUserLogEntry)
    session.commit()
    flash(u'Mitgliedschaft in Gruppe beendet', 'success')
    return redirect(url_for(".user_show", user_id=membership.user_id))


@bp.route('/json/levels')
def json_levels():
    if not request.is_xhr:
        abort(404)
    dormitory_id = request.args.get('dormitory', 0, type=int)
    levels = session.query(Room.level.label('level')).filter_by(
        dormitory_id=dormitory_id).order_by(Room.level).distinct()
    return jsonify(dict(items=[entry.level for entry in levels]))


@bp.route('/json/rooms')
def json_rooms():
    if not request.is_xhr:
        abort(404)
    dormitory_id = request.args.get('dormitory', 0, type=int)
    level = request.args.get('level', 0, type=int)
    rooms = session.query(
        Room.number.label("room_num")).filter_by(
        dormitory_id=dormitory_id, level=level).order_by(
        Room.number).distinct()
    return jsonify(dict(items=[entry.room_num for entry in rooms]))


@bp.route('/json/traffic/<int:user_id>')
def json_trafficdata(user_id):
    traffic_timespan = datetime.now() - timedelta(days=7)

    trafficvolumes = session.query(
        TrafficVolume
    ).join(
        (NetDevice, NetDevice.id == TrafficVolume.net_device_id)
    ).join(
        (Host, Host.id == NetDevice.host_id)
    ).filter(
        Host.user_id == user_id
    ).filter(
        TrafficVolume.timestamp > traffic_timespan)

    trafficvolume_in = trafficvolumes.filter(TrafficVolume.type == 'IN').all()
    trafficvolume_out = trafficvolumes.filter(TrafficVolume.type == 'OUT').all()

    tv_in = []
    for entry in trafficvolume_in:
        tv_in.append(entry.size / 1024 / 1024)
    tv_out = []
    for entry in trafficvolume_out:
        tv_out.append(entry.size / 1024 / 1024)

    trafficdata = [{ "name": 'Input', "data": tv_in, "stack": 0 },
            { "name": 'Output', "data": tv_out, "stack": 1 }]

    return jsonify({"series" : trafficdata})


@bp.route('/create', methods=['GET', 'POST'])
@nav.navigate(u"Anlegen")
@access.login_required
def create():
    form = UserCreateForm()
    if form.validate_on_submit():
        dorm = form.dormitory.data

        try:
            #ToDo: Ugly, but ... Someone can convert this is
            #      a proper property of Dormitory
            #ToDo: Also possibly slow and untested
            subnets = session.query(
                Subnet
            ).join(
                Subnet.vlans
            ).join(
                VLan.dormitories
            ).filter(
                Dormitory.id == dorm.id
            ).all()

            ip_address = host_helper.getFreeIP(subnets)
        except host_helper.SubnetFullException, error:
            flash(u'Subnetz voll', 'error')
            return render_template('user/user_create.html',
                page_title=u"Neuer Nutzer", form=form)

        hostname = host_helper.generateHostname(ip_address, form.host.data)

        room = Room.q.filter_by(number=form.room_number.data,
            level=form.level.data, dormitory_id=dorm.id).one()

        #ToDo: Which port to choose if room has more than one?
        patch_port = room.patch_ports[0]

        myUser = User(login=form.login.data,
            name=form.name.data,
            room=room,
            registration_date=datetime.now())
        plain_password = user_helper.generatePassword(12)
        #TODO: DEBUG remove in productive!!!
        print u"new password: " + plain_password
        myUser.set_password(plain_password)
        session.add(myUser)

        myHost = Host(hostname=hostname,
            user=myUser,
            room=room)
        session.add(myHost)

        myNetDevice = NetDevice(ipv4=ip_address,
            mac=form.mac.data,
            host=myHost,
            patch_port=patch_port)
        session.add(myNetDevice)
        session.commit()
        flash(u'Benutzer angelegt', 'success')
        return redirect(url_for('.user_show', user_id=myUser.id))

    return render_template('user/user_create.html',
        page_title=u"Neuer Nutzer", form=form)

@bp.route('/edit/<int:user_id>', methods=['GET', 'POST'])
@access.login_required
def edit(user_id):

    user = User.q.get(user_id)

    form = UserEditForm()

    if not form.is_submitted():
        form.name.data = user.name

        form.dormitory.data = user.room.dormitory

        levels = session.query(Room.level.label('level')).filter_by(
            dormitory_id=user.room.dormitory.id).order_by(Room.level).distinct()

        form.level.choices = [(entry.level,str(entry.level)) for entry in levels]
        form.level.data = user.room.level

        rooms = session.query(
            Room).filter_by(
            dormitory_id=user.room.dormitory.id, level=user.room.level).order_by(
            Room.number).distinct()

        form.room_number.choices = [(entry.number,str(entry.number)) for entry in rooms]
        form.room_number.data = user.room

        print type(form.room_number.data)

    if form.validate_on_submit():

        room = Room.q.filter_by(number=form.room_number.data,
            level=form.level.data, dormitory_id=form.dormitory.data.id).one()

        if len(form.name.data):
            user.name = form.name.data
        if room is not None:
            user.room = room

        session.add(user)
        session.commit()

        flash(u'Benutzer geändert', 'success')
        return redirect(url_for('.user_show', user_id=user.id))

    return render_template('user/user_edit.html', user_id=user_id,
        page_title=u"Benutzer editieren", form=form)

@bp.route('/search', methods=['GET', 'POST'])
@nav.navigate(u"Suchen")
def search():
    form = UserSearchForm()
    if form.validate_on_submit():
        userResult = User.q
        if len(form.userid.data):
            userResult = userResult.filter(User.id == form.userid.data)
        if len(form.name.data):
            userResult = userResult.filter(User.name.like('%' + form.name\
            .data + '%'))
        if len(form.login.data):
            userResult = userResult.filter(User.login == form.login.data)
        if not len(userResult.all()):
            flash(u'Benutzer nicht gefunden', 'error')
        return render_template('user/user_search.html',
            page_title=u"Suchergebnis",
            results=userResult.all(), form=form)
    return render_template('user/user_search.html', form=form)


@bp.route('/host_create', methods=['GET', 'POST'])
@nav.navigate(u"Host erstellen")
def host_create():
    form = hostCreateForm()
    hostResult = Host.q.all()
    if form.validate_on_submit():
        myHost = Host(hostname=form.name.data)
        session.add(myHost)
        session.commit()
        flash(u'Host angelegt', 'success')
        return render_template('user/host_create.html', form=form,
            results=hostResult)
    return render_template('user/host_create.html', form=form,
        results=hostResult)
