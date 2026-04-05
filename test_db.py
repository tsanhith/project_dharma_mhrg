from database.db import engine, Base
from database.models import JobPipeline

print("Creating database tables...")
Base.metadata.create_all(bind=engine)
print("Database schema created.")
