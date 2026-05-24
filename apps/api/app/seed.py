"""Seed demo data for Janavani.

Usage:
    cd apps/api
    python -m app.seed
"""

from sqlmodel import Session

from app.db import create_db_and_tables, get_engine
from app.models import Grievance, IssueCluster, User

# ── Demo users ────────────────────────────────────────────────────────

USERS = [
    {"phone": "9876543210", "name": "Ramesh Kumar", "ward": "8", "lang": "hi"},
    {"phone": "9876543211", "name": "Sunita Devi", "ward": "8", "lang": "hi"},
    {"phone": "9876543212", "name": "Amit Singh", "ward": "8", "lang": "hi"},
    {"phone": "9876543213", "name": "Priya Sharma", "ward": "8", "lang": "hi"},
    {"phone": "9876543214", "name": "Vikram Yadav", "ward": "8", "lang": "hi"},
    {"phone": "9876543215", "name": "Anita Joshi", "ward": "11", "lang": "hi"},
    {"phone": "9876543216", "name": "Rajesh Patel", "ward": "11", "lang": "hi"},
    {"phone": "9876543217", "name": "Meena Gupta", "ward": "11", "lang": "hi"},
    {"phone": "9876543218", "name": "Suresh Rao", "ward": "4", "lang": "hi"},
    {"phone": "9876543219", "name": "Kavita Nair", "ward": "4", "lang": "mr"},
]

# ── Demo grievances ───────────────────────────────────────────────────

WATER_GRIEVANCES_WARD8 = [
    ("हमारे वार्ड 8 में तीन दिन से पानी नहीं आ रहा है", "hi"),
    ("Ward 8 mein paani supply band hai kal se", "hi-Latn"),
    ("तीन दिन से नल सूखा है वार्ड 8 में", "hi"),
    ("ward 8 water nahi aa raha supply problem", "hi-Latn"),
    ("पानी की टंकी खाली है वार्ड 8", "hi"),
    ("teen din se paani ki ek boond nahi ward 8", "hi-Latn"),
    ("वार्ड नंबर 8 में जल आपूर्ति ठप है", "hi"),
    ("ward number 8 mein nal jal nahi aa raha", "hi-Latn"),
    ("paani ka tanker nahi aaya ward 8 mein", "hi-Latn"),
    ("हमारे मोहल्ले में पानी की बहुत समस्या है वार्ड 8", "hi"),
]

GARBAGE_GRIEVANCES_WARD11 = [
    ("ward 11 mein kachra nahi uth raha hafte se", "hi-Latn"),
    ("वार्ड 11 में कचरा नहीं उठ रहा है", "hi"),
    ("garbage collection band hai ward 11 mein", "hi-Latn"),
    ("कचरे का ढेर लग गया है वार्ड 11", "hi"),
    ("safai karamchari nahi aate ward 11", "hi-Latn"),
    ("वार्ड नंबर 11 की सफाई नहीं हो रही", "hi"),
    ("nala jam hai ward 11 mein", "hi-Latn"),
    ("गंदगी फैली है वार्ड 11 की गलियों में", "hi"),
]

ROAD_GRIEVANCES_WARD4 = [
    ("ward 4 mein sadak par bada gaddha hai", "hi-Latn"),
    ("वार्ड 4 की सड़क टूट गई है", "hi"),
    ("road broken hai ward 4 mein accident ho sakta", "hi-Latn"),
    ("footpath nahi hai ward 4 mein", "hi-Latn"),
    ("वार्ड 4 में सड़क पर बड़ा गड्ढा है", "hi"),
]

ELECTRICITY_WARD2 = [
    ("ward 2 mein kal se bijli nahi aa rahi", "hi-Latn"),
    ("वार्ड 2 में बिजली की समस्या है", "hi"),
    ("transformer kharab hai ward 2", "hi-Latn"),
]


# ── Main seed function ────────────────────────────────────────────────


def seed():
    engine = get_engine()
    create_db_and_tables()

    with Session(engine) as session:
        # Users
        user_objs = []
        for u in USERS:
            user = User(
                phone_number=u["phone"],
                display_name=u["name"],
                preferred_language=u["lang"],
                ward=u["ward"],
            )
            session.add(user)
            user_objs.append(user)
        session.commit()
        print(f"  Created {len(user_objs)} users")

        # Water cluster + grievances — Ward 8
        water_cluster = IssueCluster(
            title="Water shortage in Ward 8",
            summary="Multiple citizens in Ward 8 report no water supply for 3+ days. Tankers have not arrived.",
            issue_category="water_supply",
            department="water_department",
            ward="8",
            status="open",
            grievance_count=len(WATER_GRIEVANCES_WARD8),
            support_count=3,
            urgency_score=0.85,
        )
        session.add(water_cluster)
        session.commit()

        for i, (text, lang) in enumerate(WATER_GRIEVANCES_WARD8):
            g = Grievance(
                user_id=user_objs[i % 5].id,
                raw_text=text,
                normalized_text=text,
                language=lang,
                issue_category="water_supply",
                department="water_department",
                urgency="high",
                ward="8",
                pii_redacted_text=text,
                cluster_id=water_cluster.id,
                status="clustered",
                consent_public=True,
            )
            session.add(g)
        print(f"  Created {len(WATER_GRIEVANCES_WARD8)} water grievances (Ward 8)")

        # Garbage cluster + grievances — Ward 11
        garbage_cluster = IssueCluster(
            title="Garbage not collected in Ward 11",
            summary="Citizens in Ward 11 report garbage has not been collected for over a week. Piles accumulating on streets.",
            issue_category="sanitation",
            department="sanitation_department",
            ward="11",
            status="open",
            grievance_count=len(GARBAGE_GRIEVANCES_WARD11),
            support_count=2,
            urgency_score=0.70,
        )
        session.add(garbage_cluster)
        session.commit()

        for i, (text, lang) in enumerate(GARBAGE_GRIEVANCES_WARD11):
            g = Grievance(
                user_id=user_objs[5 + i % 3].id,
                raw_text=text,
                normalized_text=text,
                language=lang,
                issue_category="sanitation",
                department="sanitation_department",
                urgency="medium",
                ward="11",
                pii_redacted_text=text,
                cluster_id=garbage_cluster.id,
                status="clustered",
                consent_public=True,
            )
            session.add(g)
        print(
            f"  Created {len(GARBAGE_GRIEVANCES_WARD11)} garbage grievances (Ward 11)"
        )

        # Roads cluster — Ward 4
        road_cluster = IssueCluster(
            title="Pothole on main road Ward 4",
            summary="Large pothole on main road in Ward 4 causing accidents and traffic. Residents demand immediate repair.",
            issue_category="roads",
            department="public_works",
            ward="4",
            status="open",
            grievance_count=len(ROAD_GRIEVANCES_WARD4),
            support_count=1,
            urgency_score=0.60,
        )
        session.add(road_cluster)
        session.commit()

        for i, (text, lang) in enumerate(ROAD_GRIEVANCES_WARD4):
            g = Grievance(
                user_id=user_objs[8 + i % 2].id,
                raw_text=text,
                normalized_text=text,
                language=lang,
                issue_category="roads",
                department="public_works",
                urgency="medium",
                ward="4",
                pii_redacted_text=text,
                cluster_id=road_cluster.id,
                status="clustered",
                consent_public=True,
            )
            session.add(g)
        print(f"  Created {len(ROAD_GRIEVANCES_WARD4)} road grievances (Ward 4)")

        # Electricity — Ward 2 (ungrouped, to test new cluster creation)
        for i, (text, lang) in enumerate(ELECTRICITY_WARD2):
            g = Grievance(
                user_id=user_objs[0].id,
                raw_text=text,
                normalized_text=text,
                language=lang,
                issue_category="electricity",
                department="electricity_department",
                urgency="high",
                ward="2",
                pii_redacted_text=text,
                status="submitted",
                consent_public=True,
            )
            session.add(g)
        print(f"  Created {len(ELECTRICITY_WARD2)} electricity grievances (Ward 2)")

        session.commit()

    print("\nSeed complete!")


if __name__ == "__main__":
    seed()
