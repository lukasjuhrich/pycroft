from pycroft.model.logging import UserLogEntry, LogEntry, RoomLogEntry
from pycroft.model import session

def _create_log_entry(type, *args, **kwargs):
    """
    This method will create a new LogEntry of the given type with the given
    arguments.

    :param type: the type of the LogEntry which should be created.
    :param args: the positionals which will be passed to the constructor.
    :param kwargs: the keyword arguments which will be passed to the constructor.
    :return: the newly created LogEntry.
    """
    type = str(type).lower()

    if type == "userlogentry":
        entry = UserLogEntry(*args, **kwargs)
    elif type == "roomlogentry":
        entry = RoomLogEntry(*args, **kwargs)
    else:
        raise ValueError("Unknown LogEntry type!")

    session.session.add(entry)
    session.session.commit()

    return entry

def delete_log_entry(log_entry_id):
    """
    This method will remove the LogEntry for the given id.

    :param log_entry_id: the id of the LogEntry which should be removed.
    :return: the removed LogEntry.
    """
    entry= LogEntry.q.get(log_entry_id)
    if entry is None:
        raise ValueError("The given id is wrong!")

    if entry.discriminator == "userlogentry":
        del_entry = UserLogEntry.q.get(log_entry_id)
    elif entry.discriminator == "roomlogentry":
        del_entry = RoomLogEntry.q.get(log_entry_id)
    else:
        raise ValueError("Unknown LogEntry type!")

    session.session.delete(del_entry)
    session.session.commit()

    return del_entry


def create_user_log_entry(*args, **kwargs):
    """
    This method will create a new UserLogEntry.

    :param args: the positionals which will be passed to the constructor.
    :param kwargs: the keyword arguments which will be passed to the constructor.
    :return: the newly created UserLogEntry.
    """
    return _create_log_entry("userlogentry", *args, **kwargs)


def create_room_log_entry(*args, **kwargs):
    """
    This method will create a new RoomLogEntry.

    :param args: the positionals which will be passed to the constructor.
    :param kwargs: the keyword arguments which will be passed to the constructor.
    :return: the newly created RoomLogEntry.
    """
    return _create_log_entry("roomlogentry", *args, **kwargs)
