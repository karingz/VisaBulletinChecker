import os
import psycopg2

DB_URL = os.getenv("DATABASE_URL")  # Set this in your Vercel environment variables

def get_db_connection():
    return psycopg2.connect(DB_URL)
