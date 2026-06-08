import psycopg2
from dotenv import load_dotenv
import os

 
load_dotenv()
 
def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )
 
if __name__ == "__main__":
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT current_user;")
    print("Inloggad som:", cursor.fetchone()[0])
    conn.close()