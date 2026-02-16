# scripts/seed_merchants.py

from campaign.db import SessionLocal, init_db
from campaign.campaign_models import Merchant
import uuid

def seed():
    init_db()
    session = SessionLocal()

    merchants = [
        # Merchant(
        #     id=str(uuid.uuid4()),
        #     name="Test Merchant 1",   
        #     phone="+919999999004"
        # ),
        # Merchant(
        #     id=str(uuid.uuid4()),
        #     name="Test Merchant 2",
        #     phone="+919999999005"
        # ),
        Merchant(
            id=str(uuid.uuid4()),
            name="Gaurav",
            phone="+91000000003"
        ),
        Merchant(
            id=str(uuid.uuid4()),
            name="Raju",
            phone="+91000000009"
        ),
    ]

    session.add_all(merchants)
    session.commit()
    session.close()
    print("✅ Merchants seeded")

if __name__ == "__main__":
    seed()

