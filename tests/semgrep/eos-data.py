# Fixtures for core/scaffold/db-safety/semgrep-data.yml (semgrep --test). Not executed.
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy import Column, Float, Numeric
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Order(Base):
    # ruleid: eos-money-float-orm-python
    amount: Mapped[float] = mapped_column()
    # ruleid: eos-money-float-orm-python
    total_price = Column(Float)
    # ruleid: eos-money-float-orm-python
    tax: Mapped[float] = mapped_column(sa.Float(precision=53))
    # ruleid: eos-money-float-orm-python
    fee_cents: Mapped[float]
    # ok: eos-money-float-orm-python
    amount2: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    # ok: eos-money-float-orm-python
    latitude: Mapped[float] = mapped_column()
    # ok: eos-money-float-orm-python
    price = Column(Numeric(12, 2), nullable=False)


def charge(payload, order):
    # ruleid: eos-money-float-conversion
    amount = float(payload["amount"])
    # ruleid: eos-money-float-conversion
    order.total = float(order.subtotal_cents) / 100
    # ruleid: eos-money-float-conversion
    fee = Decimal(0.1)  # noqa: RUF032 - deliberate bad example
    # ok: eos-money-float-conversion
    ratio = float(payload["ratio"])
    # ok: eos-money-float-conversion
    fee2 = Decimal("0.10")
    return amount, ratio, fee, fee2


class Pricing(Base):
    # ok: eos-money-float-orm-python
    tax_rate: Mapped[float] = mapped_column()
    # ok: eos-money-float-orm-python
    discount_pct = Column(Float)
    # ruleid: eos-money-float-orm-python
    account_balance = Column(Float)
    # ruleid: eos-money-float-orm-python
    duration_fee: Mapped[float]
