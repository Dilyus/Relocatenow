from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    favorites: Mapped[list["Favorite"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    history_items: Mapped[list["SearchHistory"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class City(Base):
    __tablename__ = "cities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    region: Mapped[str] = mapped_column(String(160), nullable=False)
    population: Mapped[int] = mapped_column(Integer, nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    avg_rent_usd: Mapped[float] = mapped_column(Float, nullable=False)
    climate_score: Mapped[float] = mapped_column(Float, nullable=False)
    sea_score: Mapped[float] = mapped_column(Float, nullable=False)
    internet_score: Mapped[float] = mapped_column(Float, nullable=False)
    safety_score: Mapped[float] = mapped_column(Float, nullable=False)
    ecology_score: Mapped[float] = mapped_column(Float, nullable=False)
    infrastructure_score: Mapped[float] = mapped_column(Float, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    pros: Mapped[str] = mapped_column(Text, default="")
    cons: Mapped[str] = mapped_column(Text, default="")
    transport_info: Mapped[str] = mapped_column(Text, default="")
    education_info: Mapped[str] = mapped_column(Text, default="")
    healthcare_info: Mapped[str] = mapped_column(Text, default="")
    job_info: Mapped[str] = mapped_column(Text, default="")
    monthly_budget_usd: Mapped[int] = mapped_column(Integer, default=0)
    suitable_for: Mapped[str] = mapped_column(Text, default="")
    relocation_summary: Mapped[str] = mapped_column(Text, default="")

    favorites: Mapped[list["Favorite"]] = relationship(
        back_populates="city", cascade="all, delete-orphan"
    )
    attractions: Mapped[list["Attraction"]] = relationship(
        back_populates="city", cascade="all, delete-orphan"
    )
    stats: Mapped[list["CityStats"]] = relationship(
        back_populates="city", cascade="all, delete-orphan", order_by="CityStats.updated_at.desc()"
    )


class Favorite(Base):
    __tablename__ = "favorites"
    __table_args__ = (UniqueConstraint("user_id", "city_id", name="uix_user_city"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    city_id: Mapped[int] = mapped_column(ForeignKey("cities.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    user: Mapped[User] = relationship(back_populates="favorites")
    city: Mapped[City] = relationship(back_populates="favorites")


class SearchHistory(Base):
    __tablename__ = "search_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    max_rent_usd: Mapped[float] = mapped_column(Float, nullable=False)
    climate_preference: Mapped[str] = mapped_column(String(40), nullable=False)
    sea_preference: Mapped[str] = mapped_column(String(40), nullable=False)
    safety_important: Mapped[str] = mapped_column(String(10), nullable=False)
    internet_important: Mapped[str] = mapped_column(String(10), nullable=False)
    ecology_important: Mapped[str] = mapped_column(String(10), nullable=False)
    infrastructure_important: Mapped[str] = mapped_column(String(10), nullable=False)
    best_city: Mapped[str] = mapped_column(String(120), default="")
    best_score: Mapped[float] = mapped_column(Float, default=0)

    user: Mapped[User] = relationship(back_populates="history_items")


class Attraction(Base):
    __tablename__ = "attractions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    city_id: Mapped[int] = mapped_column(ForeignKey("cities.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)

    city: Mapped[City] = relationship(back_populates="attractions")


class CityStats(Base):
    __tablename__ = "city_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    city_id: Mapped[int] = mapped_column(ForeignKey("cities.id"), nullable=False)
    avg_rent_price: Mapped[float] = mapped_column(Float, nullable=False)
    avg_buy_price_m2: Mapped[float] = mapped_column(Float, nullable=False)
    crime_level: Mapped[str] = mapped_column(String(80), nullable=False)
    safety_level: Mapped[str] = mapped_column(String(80), nullable=False)
    source_name: Mapped[str] = mapped_column(String(160), default="Учебные данные")
    source_url: Mapped[str] = mapped_column(String(255), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    city: Mapped[City] = relationship(back_populates="stats")
