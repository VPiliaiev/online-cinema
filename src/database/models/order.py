from enum import Enum
from sqlalchemy import Integer, ForeignKey, DateTime, Enum as SQLEnum, Float
from sqlalchemy.orm import relationship, Mapped, mapped_column
from datetime import datetime
from database import Base


class OrderStatusEnum(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    CANCELED = "canceled"


class OrderModel(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    status: Mapped[OrderStatusEnum] = mapped_column(
        SQLEnum(OrderStatusEnum),
        default=OrderStatusEnum.PENDING,
        nullable=False
    )
    total_amount: Mapped[float] = mapped_column(Float, nullable=True)

    user = relationship("UserModel", back_populates="orders")
    items = relationship("OrderItemModel", back_populates="order", cascade="all, delete-orphan")


class OrderItemModel(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id"), nullable=False)
    movie_id: Mapped[int] = mapped_column(Integer, ForeignKey("movies.id"), nullable=False)
    price_at_order: Mapped[float] = mapped_column(Float, nullable=False)

    order = relationship("OrderModel", back_populates="items")
    movie = relationship("MovieModel")
