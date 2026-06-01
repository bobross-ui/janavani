"""Seed demo data for Janavani.

Usage:
    cd apps/api
    python -m app.seed
"""

from sqlmodel import Session

from app.db import create_db_and_tables, get_engine
from app.models import Grievance, IssueCluster, User
from app.models import _new_uuid
from app.services.embeddings import embed_to_json

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
    {"phone": "0000000000", "name": "Demo User", "ward": "8", "lang": "en",
     "id": "demo-user-1"},
]

# ── Mumbai ward coordinates for demo map ─────────────────────────────

# (approximate centroids for demo visibility)
WARD_COORDS = {
    "2": (19.028, 72.849),   # Bandra West
    "4": (18.995, 72.835),   # Byculla
    "8": (19.043, 72.857),   # Khar West (matches geocoding)
    "11": (19.107, 72.856),  # Andheri West
}

# ── Demo grievances ───────────────────────────────────────────────────

WATER_GRIEVANCES_WARD8 = [
    # (raw_text, language, english_normalized_text)
    ("हमारे वार्ड 8 में तीन दिन से पानी नहीं आ रहा है", "hi",
     "no water supply in ward 8 for three days"),
    ("Ward 8 mein paani supply band hai kal se", "hi-Latn",
     "water supply is off in ward 8 since yesterday"),
    ("तीन दिन से नल सूखा है वार्ड 8 में", "hi",
     "taps have been dry for three days in ward 8"),
    ("ward 8 water nahi aa raha supply problem", "hi-Latn",
     "water not coming supply problem in ward 8"),
    ("पानी की टंकी खाली है वार्ड 8", "hi",
     "water tank is empty in ward 8"),
    ("teen din se paani ki ek boond nahi ward 8", "hi-Latn",
     "not a single drop of water for three days in ward 8"),
    ("वार्ड नंबर 8 में जल आपूर्ति ठप है", "hi",
     "water supply is down in ward number 8"),
    ("ward number 8 mein nal jal nahi aa raha", "hi-Latn",
     "tap water not coming in ward number 8"),
    ("paani ka tanker nahi aaya ward 8 mein", "hi-Latn",
     "water tanker did not come in ward 8"),
    ("हमारे मोहल्ले में पानी की बहुत समस्या है वार्ड 8", "hi",
     "severe water problem in our neighborhood ward 8"),
]

GARBAGE_GRIEVANCES_WARD11 = [
    # (raw_text, language, english_normalized_text)
    ("ward 11 mein kachra nahi uth raha hafte se", "hi-Latn",
     "garbage not being collected in ward 11 for a week"),
    ("वार्ड 11 में कचरा नहीं उठ रहा है", "hi",
     "garbage is not being picked up in ward 11"),
    ("garbage collection band hai ward 11 mein", "hi-Latn",
     "garbage collection is stopped in ward 11"),
    ("कचरे का ढेर लग गया है वार्ड 11", "hi",
     "garbage pile has accumulated in ward 11"),
    ("safai karamchari nahi aate ward 11", "hi-Latn",
     "cleaning workers do not come to ward 11"),
    ("वार्ड नंबर 11 की सफाई नहीं हो रही", "hi",
     "ward number 11 is not being cleaned"),
    ("nala jam hai ward 11 mein", "hi-Latn",
     "drain is blocked in ward 11"),
    ("गंदगी फैली है वार्ड 11 की गलियों में", "hi",
     "filth is spread in the lanes of ward 11"),
]

ROAD_GRIEVANCES_WARD4 = [
    # (raw_text, language, english_normalized_text)
    ("ward 4 mein sadak par bada gaddha hai", "hi-Latn",
     "big pothole on road in ward 4"),
    ("वार्ड 4 की सड़क टूट गई है", "hi",
     "road in ward 4 is broken"),
    ("road broken hai ward 4 mein accident ho sakta", "hi-Latn",
     "road is broken in ward 4 accident may happen"),
    ("footpath nahi hai ward 4 mein", "hi-Latn",
     "no footpath in ward 4"),
    ("वार्ड 4 में सड़क पर बड़ा गड्ढा है", "hi",
     "big pothole on road in ward 4"),
]

ELECTRICITY_WARD2 = [
    # (raw_text, language, english_normalized_text)
    ("ward 2 mein kal se bijli nahi aa rahi", "hi-Latn",
     "no electricity in ward 2 since yesterday"),
    ("वार्ड 2 में बिजली की समस्या है", "hi",
     "electricity problem in ward 2"),
    ("transformer kharab hai ward 2", "hi-Latn",
     "transformer broken in ward 2"),
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
                id=u.get("id", _new_uuid()),
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
        w8_lat, w8_lon = WARD_COORDS["8"]
        water_cluster = IssueCluster(
            title="Water Supply, Ward 8",
            summary="Multiple citizens in Ward 8 report no water supply for 3+ days. Tankers have not arrived.",
            issue_category="water_supply",
            department="water_department",
            ward="8",
            area="Khar West",
            area_source="demo_mumbai",
            suburb="Khar West",
            road="S.V. Road",
            status="open",
            grievance_count=len(WATER_GRIEVANCES_WARD8),
            support_count=3,
            urgency_score=0.85,
            centroid_latitude=w8_lat,
            centroid_longitude=w8_lon,
            coordinate_count=len(WATER_GRIEVANCES_WARD8),
        )
        water_cluster.centroid_embedding_json = embed_to_json(water_cluster.summary)
        water_cluster.embedding_count = len(WATER_GRIEVANCES_WARD8)
        session.add(water_cluster)
        session.commit()

        for i, (text, lang, norm) in enumerate(WATER_GRIEVANCES_WARD8):
            g = Grievance(
                user_id=user_objs[i % 5].id,
                raw_text=text,
                normalized_text=norm,
                embedding_json=embed_to_json(norm),
                language=lang,
                issue_category="water_supply",
                department="water_department",
                urgency="high",
                ward="8",
                latitude=w8_lat,
                longitude=w8_lon,
                pii_redacted_text=text,
                cluster_id=water_cluster.id,
                status="clustered",
                area="Khar West",
                area_source="demo_mumbai",
                consent_public=True,
            )
            session.add(g)
        print(f"  Created {len(WATER_GRIEVANCES_WARD8)} water grievances (Ward 8)")

        # Garbage cluster + grievances — Ward 11
        w11_lat, w11_lon = WARD_COORDS["11"]
        garbage_cluster = IssueCluster(
            title="Sanitation, Ward 11",
            summary="Citizens in Ward 11 report garbage has not been collected for over a week. Piles accumulating on streets.",
            issue_category="sanitation",
            department="sanitation_department",
            ward="11",
            area="Andheri West",
            area_source="demo_mumbai",
            suburb="Andheri West",
            road="Lokhandwala Road",
            status="open",
            grievance_count=len(GARBAGE_GRIEVANCES_WARD11),
            support_count=2,
            urgency_score=0.70,
            centroid_latitude=w11_lat,
            centroid_longitude=w11_lon,
            coordinate_count=len(GARBAGE_GRIEVANCES_WARD11),
        )
        garbage_cluster.centroid_embedding_json = embed_to_json(garbage_cluster.summary)
        garbage_cluster.embedding_count = len(GARBAGE_GRIEVANCES_WARD11)
        session.add(garbage_cluster)
        session.commit()

        for i, (text, lang, norm) in enumerate(GARBAGE_GRIEVANCES_WARD11):
            g = Grievance(
                user_id=user_objs[5 + i % 3].id,
                raw_text=text,
                normalized_text=norm,
                embedding_json=embed_to_json(norm),
                language=lang,
                issue_category="sanitation",
                department="sanitation_department",
                urgency="medium",
                ward="11",
                latitude=w11_lat,
                longitude=w11_lon,
                pii_redacted_text=text,
                cluster_id=garbage_cluster.id,
                status="clustered",
                area="Andheri West",
                area_source="demo_mumbai",
                consent_public=True,
            )
            session.add(g)
        print(
            f"  Created {len(GARBAGE_GRIEVANCES_WARD11)} garbage grievances (Ward 11)"
        )

        # Roads cluster — Ward 4
        w4_lat, w4_lon = WARD_COORDS["4"]
        road_cluster = IssueCluster(
            title="Roads, Ward 4",
            summary="Large pothole on main road in Ward 4 causing accidents and traffic. Residents demand immediate repair.",
            issue_category="roads",
            department="public_works",
            ward="4",
            area="Byculla",
            area_source="demo_mumbai",
            suburb="Byculla",
            road="Clare Road",
            status="open",
            grievance_count=len(ROAD_GRIEVANCES_WARD4),
            support_count=1,
            urgency_score=0.60,
            centroid_latitude=w4_lat,
            centroid_longitude=w4_lon,
            coordinate_count=len(ROAD_GRIEVANCES_WARD4),
        )
        road_cluster.centroid_embedding_json = embed_to_json(road_cluster.summary)
        road_cluster.embedding_count = len(ROAD_GRIEVANCES_WARD4)
        session.add(road_cluster)
        session.commit()

        for i, (text, lang, norm) in enumerate(ROAD_GRIEVANCES_WARD4):
            g = Grievance(
                user_id=user_objs[8 + i % 2].id,
                raw_text=text,
                normalized_text=norm,
                embedding_json=embed_to_json(norm),
                language=lang,
                issue_category="roads",
                department="public_works",
                urgency="medium",
                ward="4",
                latitude=w4_lat,
                longitude=w4_lon,
                pii_redacted_text=text,
                cluster_id=road_cluster.id,
                status="clustered",
                area="Byculla",
                area_source="demo_mumbai",
                consent_public=True,
            )
            session.add(g)
        print(f"  Created {len(ROAD_GRIEVANCES_WARD4)} road grievances (Ward 4)")

        # Electricity — Ward 2 (ungrouped, to test new cluster creation)
        w2_lat, w2_lon = WARD_COORDS["2"]
        for i, (text, lang, norm) in enumerate(ELECTRICITY_WARD2):
            g = Grievance(
                user_id=user_objs[0].id,
                raw_text=text,
                normalized_text=norm,
                embedding_json=embed_to_json(norm),
                language=lang,
                issue_category="electricity",
                department="electricity_department",
                urgency="high",
                ward="2",
                latitude=w2_lat,
                longitude=w2_lon,
                pii_redacted_text=text,
                status="submitted",
                area="Bandra West",
                area_source="demo_mumbai",
                consent_public=True,
            )
            session.add(g)
        print(f"  Created {len(ELECTRICITY_WARD2)} electricity grievances (Ward 2)")

        session.commit()

    print("\nSeed complete!")


if __name__ == "__main__":
    seed()