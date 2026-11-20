"""Print a fresh one-time pairing code for the seeded local demo older adult.

Run from Dev/Backend after `python -m scripts.seed`:
    python -m scripts.demo_pairing_code
"""

from sqlalchemy import select

from app.db import SessionLocal
from app.model.entities import ConsentGrant, User
from app.model.services.auth_service import create_pairing_code
from scripts.seed import CAREGIVER_EMAIL, MARGARET_NAME


def main() -> None:
    with SessionLocal() as db:
        caregiver = db.scalar(select(User).where(User.email == CAREGIVER_EMAIL))
        if caregiver is None:
            raise SystemExit("Demo caregiver is missing. Run python -m scripts.seed first.")
        margaret = db.scalar(
            select(User)
            .join(ConsentGrant, ConsentGrant.older_adult_id == User.id)
            .where(
                ConsentGrant.caregiver_id == caregiver.id,
                User.display_name == MARGARET_NAME,
            )
        )
        if margaret is None:
            raise SystemExit("Demo older adult is missing. Run python -m scripts.seed first.")
        code, expires_at = create_pairing_code(db, actor=caregiver, older_adult_id=margaret.id)
    print(f"Maggie's one-time pairing code: {code}")
    print(f"Expires: {expires_at.isoformat()}")


if __name__ == "__main__":
    main()
