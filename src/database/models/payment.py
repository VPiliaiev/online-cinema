from enum import Enum
from sqlalchemy import Integer, ForeignKey, DateTime, Enum as SQLEnum, Float, String
from sqlalchemy.orm import relationship, Mapped, mapped_column
from datetime import datetime
from database import Base


class PaymentStatusEnum(str, Enum):
    PENDING = "pending"
    SUCCESSFUL = "successful"
    CANCELED = "canceled"
    REFUNDED = "refunded"


class PaymentModel(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id"), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    external_payment_id: Mapped[str] = mapped_column(String, nullable=True)
    status: Mapped[PaymentStatusEnum] = mapped_column(
        SQLEnum(PaymentStatusEnum),
        default=PaymentStatusEnum.PENDING,
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    user = relationship("UserModel", back_populates="payments")
    order = relationship("OrderModel", back_populates="payments")
    items = relationship("PaymentItemModel", back_populates="payment", cascade="all, delete-orphan")


class PaymentItemModel(Base):
    __tablename__ = "payment_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    payment_id: Mapped[int] = mapped_column(Integer, ForeignKey("payments.id"), nullable=False)
    order_item_id: Mapped[int] = mapped_column(Integer, ForeignKey("order_items.id"), nullable=False)
    price_at_payment: Mapped[float] = mapped_column(Float, nullable=False)
    payment = relationship("PaymentModel", back_populates="items")
    order_item = relationship("OrderItemModel")
