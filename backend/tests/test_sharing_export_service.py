from datetime import datetime, timezone
import pytest

from app.database.session import AsyncSessionLocal
from app.models import Conversation, Recording, User, MOM
from app.services.mom_service import approve_mom, generate_mom_for_conversation
from app.services.sharing_export_service import (
    export_mom,
    get_mom_shares,
    revoke_mom_share,
    share_mom,
)


@pytest.mark.asyncio
async def test_sharing_and_export_approval_gating():
    async with AsyncSessionLocal() as db:
        user = User(auth_id="auth0|user_sharing_1")
        db.add(user)
        await db.flush()

        rec = Recording(user_id=user.id, duration_ms=10000, state="completed")
        db.add(rec)
        await db.flush()

        conv = Conversation(
            user_id=user.id,
            recording_id=rec.id,
            title="Roadmap Discussion",
            occurred_at=datetime.now(timezone.utc),
        )
        db.add(conv)
        await db.commit()

        # Generate draft MOM
        mom = await generate_mom_for_conversation(db, conv.id, user.id)
        assert mom.status == "draft"

        # 1. Attempting to share an unapproved MOM MUST fail
        with pytest.raises(ValueError) as exc_info:
            await share_mom(db, mom.id, user.id, "stakeholder@example.com")
        assert "Unapproved MOM cannot be shared" in str(exc_info.value)

        # 2. Attempting to export an unapproved MOM MUST fail
        with pytest.raises(ValueError) as exc_info:
            await export_mom(db, mom.id, user.id, "markdown")
        assert "Unapproved MOM cannot be exported" in str(exc_info.value)

        # 3. Approve MOM
        await approve_mom(db, mom.id, user.id)

        # 4. Now sharing approved MOM must succeed
        share = await share_mom(db, mom.id, user.id, "stakeholder@example.com")
        assert share.id is not None
        assert share.share_token is not None

        # List shares
        shares = await get_mom_shares(db, mom.id, user.id)
        assert len(shares) == 1

        # Revoke share
        revoked = await revoke_mom_share(db, share.id, user.id)
        assert revoked.is_revoked is True

        # 5. Export approved MOM in Markdown, JSON, PDF formats
        md_export = await export_mom(db, mom.id, user.id, "markdown")
        assert "# MOM - Roadmap Discussion" in md_export["content"]

        json_export = await export_mom(db, mom.id, user.id, "json")
        assert "Roadmap Discussion" in json_export["content"]

        pdf_export = await export_mom(db, mom.id, user.id, "pdf")
        assert "%PDF-1.4" in pdf_export["content"]


@pytest.mark.asyncio
async def test_sharing_export_user_ownership_isolation():
    async with AsyncSessionLocal() as db:
        user_a = User(auth_id="auth0|user_sharing_a")
        user_b = User(auth_id="auth0|user_sharing_b")
        db.add_all([user_a, user_b])
        await db.flush()

        rec = Recording(user_id=user_a.id, duration_ms=5000, state="completed")
        db.add(rec)
        await db.flush()

        conv = Conversation(
            user_id=user_a.id,
            recording_id=rec.id,
            title="Secret Strategy",
            occurred_at=datetime.now(timezone.utc),
        )
        db.add(conv)
        await db.commit()

        mom = await generate_mom_for_conversation(db, conv.id, user_a.id)
        await approve_mom(db, mom.id, user_a.id)

        # User B attempting to share or export User A's MOM must fail
        with pytest.raises(ValueError):
            await share_mom(db, mom.id, user_b.id, "leak@example.com")

        with pytest.raises(ValueError):
            await export_mom(db, mom.id, user_b.id, "json")
