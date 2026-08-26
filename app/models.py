from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)

    jobs = relationship(
        "Job",
        back_populates="owner",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    company = Column(String, nullable=False)
    role = Column(String, nullable=False)
    status = Column(String, nullable=False, default="applied", server_default="applied")

    # Indexed because every job query filters on it, and ON DELETE CASCADE so
    # removing a user cannot leave orphaned rows behind.
    owner_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    owner = relationship("User", back_populates="jobs")
