"""
Populate data/users.json with a handful of demo accounts so Donor Search
and Request Form have something to match against on a fresh checkout.

Run once, from the backend/ directory, after installing requirements:
    python seed_data.py

Every seeded account uses the password:  Passw0rd!
"""
from core.auth import hash_password
from core.database import write_all

DEMO_PASSWORD = "Passw0rd!"

# Roughly spread around central Indore so radius search has something to find.
DEMO_USERS = [
    {"name": "Aarav Sharma", "email": "aarav.donor@example.com", "role": "donor",
     "blood_group": "O+", "city": "Indore", "latitude": 22.7196, "longitude": 75.8577,
     "phone": "9000000001"},
    {"name": "Priya Nair", "email": "priya.donor@example.com", "role": "donor",
     "blood_group": "O-", "city": "Indore", "latitude": 22.7280, "longitude": 75.8650,
     "phone": "9000000002"},
    {"name": "Rohan Mehta", "email": "rohan.donor@example.com", "role": "donor",
     "blood_group": "B+", "city": "Indore", "latitude": 22.7050, "longitude": 75.8450,
     "phone": "9000000003"},
    {"name": "Sneha Kulkarni", "email": "sneha.donor@example.com", "role": "both",
     "blood_group": "O+", "city": "Indore", "latitude": 22.7400, "longitude": 75.8800,
     "phone": "9000000004"},
    {"name": "Karan Verma", "email": "karan.recipient@example.com", "role": "recipient",
     "blood_group": "AB+", "city": "Indore", "latitude": 22.7196, "longitude": 75.8577,
     "phone": "9000000005"},
]


def main() -> None:
    users = []
    for i, u in enumerate(DEMO_USERS, start=1):
        users.append({
            "user_id": f"user_{i:04d}",
            "name": u["name"],
            "email": u["email"],
            "password_hash": hash_password(DEMO_PASSWORD),
            "phone": u["phone"],
            "role": u["role"],
            "blood_group": u["blood_group"],
            "city": u["city"],
            "latitude": u["latitude"],
            "longitude": u["longitude"],
            "available": True,
            "last_donation_date": None,
        })

    write_all("users", users)
    write_all("requests", [])
    print(f"Seeded {len(users)} demo users. Password for all: {DEMO_PASSWORD}")


if __name__ == "__main__":
    main()
