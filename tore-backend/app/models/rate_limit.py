from __future__ import annotations

from sqlalchemy import BigInteger, Column, Integer, String

from db import Base


class RateLimitBucket(Base):
    __tablename__ = "rate_limit_buckets"

    bucket_key = Column(String(128), primary_key=True)
    window_started_at_ms = Column(BigInteger, nullable=False)
    request_count = Column(Integer, nullable=False)
    updated_at_ms = Column(BigInteger, nullable=False, index=True)
