"""DB-backed image queue, claimed atomically across processes; restart never replays generation."""

import asyncio
import logging

from sqlalchemy import or_
from sqlmodel import select

from app.core.time import now
from app.db.models.image_generation import ImageJob
from app.db.session import SessionLocal
from app.services.image_generation_service import ImageGenerationService

logger = logging.getLogger(__name__)


async def image_worker():
    while True:
        try:
            async with SessionLocal() as session:
                service = ImageGenerationService(session)
                await service.recover_expired()
                job_id = (
                    await session.exec(
                        select(ImageJob.id)
                        .where(
                            ImageJob.status.in_(["queued", "saving"]),
                            or_(ImageJob.lease_until.is_(None), ImageJob.lease_until < now()),
                        )
                        .order_by(ImageJob.created_at)
                        .limit(1)
                    )
                ).first()
                if job_id:
                    await service.run(job_id)
                    continue
        except asyncio.CancelledError:
            raise
        except Exception:
            # No vendor response, credential, or signed URL may enter logs.
            logger.warning("Image queue unavailable; check database migration and local storage.")
        await asyncio.sleep(2)
