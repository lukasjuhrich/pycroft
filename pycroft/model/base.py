# -*- coding: utf-8 -*-
# Copyright (c) 2015 The Pycroft Authors. See the AUTHORS file.
# This file is part of the Pycroft project and licensed under the terms of
# the Apache License, Version 2.0. See the LICENSE file for details.
"""
    pycroft.model.base
    ~~~~~~~~~~~~~~

    This module contains base stuff for all models.

    :copyright: (c) 2011 by AG DSN.
"""
import re

from sqlalchemy import Column
from sqlalchemy.ext.declarative import (
    DeclarativeMeta, as_declarative, declared_attr)
from sqlalchemy.types import Integer

from pycroft.model.session import session


class _ModelMeta(DeclarativeMeta):
    """Metaclass for all mapped Database objects."""
    @property
    def q(cls):
        """This is a shortcut for easy querying of whole objects.

        With this metaclass shortcut you can query a Model with
        Model.q.filter(...) without using the verbose session stuff
        """
        return session.query(cls)


@as_declarative(metaclass=_ModelMeta)
class ModelBase(object):
    """Base class for all database models."""

    @declared_attr
    def __tablename__(cls):
        """Autogenerate the tablename for the mapped objects."""
        return cls._to_snake_case(cls.__name__)

    @staticmethod
    def _to_snake_case(name):
        name = re.sub(r"([A-Z]+)([A-Z][a-z])", r'\1_\2', name)
        name = re.sub(r"([a-z\d])([A-Z])", r'\1_\2', name)
        return name.lower()

    def __repr__(self):
        return "{0}.{1}({2})".format(
            self.__module__, self.__class__.__name__,
            ", ".join("{0}={1!r}".format(key, getattr(self, key, "<unknown>"))
                      for key in self.__mapper__.columns.keys()))


class IntegerIdModel(ModelBase):
    """
    Abstract base class for database models with an Integer primary column,
    named ``id``.
    """

    __abstract__ = True

    id = Column(Integer, primary_key=True)
