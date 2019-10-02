# Stubs for pycroft.model.base (Python 3.7)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.
from sqlalchemy import Table, MetaData
from sqlalchemy.ext.declarative import DeclarativeMeta
from typing import Any, Dict

from sqlalchemy.orm import Query


class _ModelMeta(DeclarativeMeta):
    @property
    def q(cls): ...

class ModelBase:
    def __tablename__(cls): ...
    def __init__(self, **kw): ...
    __table__: Table
    __mapper_args__: Dict[str, Any]
    q: Query
    metadata: MetaData

class IntegerIdModel(ModelBase):
    __abstract__: bool = ...
    id: Any = ...
