import os
from dotenv import load_dotenv

load_dotenv()

user = os.getenv("PG_USER")
password = os.getenv("PG_PASSWORD")
host = os.getenv("PG_HOST")
database = os.getenv("PG_DB")
port = os.getenv("PG_PORT")
debug = os.getenv("FLASK_DEBUG")

DATABASE_CONNECTION_URI = (
    f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}"
)
