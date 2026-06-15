import sqlite3

with open("seed.sql", "r") as f:
    sql = f.read()

con = sqlite3.connect("insights.db")
con.executescript(sql)
con.close()

print("insights.db created from seed.sql")
