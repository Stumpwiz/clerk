import sys
from sqlalchemy.orm import Session
from app.db.base import SessionLocal
from app.db.models import User


def add_user(email: str, username: str, role: str = "user"):
    """Add a new authorized user to the database"""
    if role not in ["admin", "user"]:
        print("❌ Error: role must be 'admin' or 'user'")
        sys.exit(1)

    db: Session = SessionLocal()
    try:
        # Check if user already exists
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            print(f"⚠️  User with email {email} already exists")
            print(f"   Current: {existing.username} ({existing.role})")

            # Update role if different
            if existing.role != role:
                existing.role = role
                db.commit()
                print(f"✅ Updated role to: {role}")
            return

        # Create new user
        new_user = User(
            username=username,
            email=email,
            role=role,
        )
        db.add(new_user)
        db.commit()
        print(f"✅ User created: {username} ({email}) - Role: {role}")
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) < 3 or len(sys.argv) > 4:
        print("Usage: python add_user.py <email> <username> [role]")
        print("  role: 'admin' or 'user' (default: 'user')")
        print("\nExample:")
        print("  python add_user.py john@example.com 'John Doe' admin")
        sys.exit(1)

    email = sys.argv[1]
    username = sys.argv[2]
    role = sys.argv[3] if len(sys.argv) == 4 else "user"

    add_user(email, username, role)
