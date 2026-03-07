"""Script to create the first admin user."""
from app.core.database import SessionLocal
from app.models.admin import Admin
from app.core.security import pwd_context


def create_admin():
    """Create a default admin user."""
    db = SessionLocal()
    
    try:
        # Check if admin already exists
        existing_admin = db.query(Admin).filter(Admin.username == "admin").first()
        
        if existing_admin:
            # Update password hash to ensure bcrypt compatibility
            existing_admin.password_hash = pwd_context.hash("admin123")
            db.commit()
            db.refresh(existing_admin)
            print("Admin user updated successfully!")
            print("Username: admin")
            print("Password: admin123")
            print(f"ID: {existing_admin.id}")
            print("\n⚠️  IMPORTANT: Change this password immediately in production!")
            return
        
        # Create new admin
        admin = Admin(
            username="admin",
            password_hash=pwd_context.hash("admin123"),  # Change this password!
        )
        
        db.add(admin)
        db.commit()
        db.refresh(admin)
        
        print(f"Admin user created successfully!")
        print(f"Username: admin")
        print(f"Password: admin123")
        print(f"ID: {admin.id}")
        print("\n⚠️  IMPORTANT: Change this password immediately in production!")
        
    except Exception as e:
        print(f"Error creating admin: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    create_admin()
