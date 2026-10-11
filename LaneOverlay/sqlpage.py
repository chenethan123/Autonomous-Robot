import sqlite3

# sets up the actual sqlite databse as login.db
database = sqlite3.connect('login.db')

# creates the cursor object which is importing in interacting with the database.
cursor = database.cursor()

# create the database with the different columns required. This is only if the database doesn't exist.
cursor.execute(''' CREATE TABLE IF NOT EXISTS logindata
       (userid     INTEGER PRIMARY KEY, 
       username TEXT,
       password TEXT,
       first_name TEXT,
       last_name TEXT)
       ''')

#applies all changes to the database
database.commit()
