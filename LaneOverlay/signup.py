# imports the random library so that a random user id can be made
import random

# imports important tinker libraries for the GUI
from tkinter import *
import tkinter as tk

root = Tk()
from tkinter import ttk
from tkinter import messagebox

# creates the tk gui
root.geometry()
root.geometry("510x1020")
root.title("Sign Up")

from datetime import datetime

# imports the sqlite3 library to be able to use sqlite database
import sqlite3

database = sqlite3.connect('login.db')

cursor = database.cursor()

# imports the hashlib library which is necessary in encrypting passwords.
import hashlib

# sets up the username password, name, etc. to be strings
username = StringVar()
password = StringVar()
firstname = StringVar()
lastname = StringVar()

# allows the username, password, firstname, and lastname to be filled in. Also sets up their location.
user_name = Entry(root, textvariable=username)
user_name.grid(row=0, column=0)
# the show part makes it so that the password appears as astericks
passw = Entry(root, textvariable=password, show='*')
passw.grid(row=2, column=0)
firstn = Entry(root, textvariable=firstname)
firstn.grid(row=0, column=1)
lastn = Entry(root, textvariable=lastname)
lastn.grid(row=2, column=1)

# labels are created to label the text boxes with what to input
user_name_label = Label(root, text="Enter your username.")
user_name_label.grid(row=1, column=0)
passw_label = Label(root, text="Enter your password.")
passw_label.grid(row=3, column=0)
first_name_label = Label(root, text="Enter your first name.")
first_name_label.grid(row=1, column=1)
last_name_label = Label(root, text="Enter your last name.")
last_name_label.grid(row=3, column=1)


# the main function needed as this controls the signing in part of the program. this creates the user's account
def signingin():
    # retrieves the username inputted
    usernamefin = user_name.get()
    # encodes the password inputted
    passwordencode = passw.get().encode("utf-8")
    passwordfin = hashlib.sha512(passwordencode).hexdigest()
    # retrieves the first name inputted
    firstnamefin = firstn.get()
    # retrieves the last name inputted
    lastnamefin = lastn.get()
    # creates a userid between 100000000 and 999999999
    userid = random.randrange(100000000, 999999999)

    # activates the database again in case it wasn't already set up
    cursor.execute(''' CREATE TABLE IF NOT EXISTS logindata
         (userid     INTEGER PRIMARY KEY, 
         username TEXT,
         password TEXT,
         first_name TEXT,
         last_name TEXT)
         ''')

    # commits this to the database
    database.commit()

    # inserts the data of the user id, username, encrypted password, first name, and last name into the database
    cursor.execute(f'''INSERT INTO logindata (userid, username, 
  password, first_name, last_name)
  VALUES (?, ?, ?, ?, ?)''',
                   (userid, usernamefin, passwordfin, firstnamefin, lastnamefin))

    # commits this to the database so that it is saved
    database.commit()

    # announces the user's success in creating an account. tells them their username in case they forgot

    openFile = open(f"{usernamefin}.txt", "a")

    time = datetime.now()
    current_hour = time.strftime("%H")
    hourint = int(current_hour) - 5
    if hourint < 0:
        hourint = 24 + hourint
    current_time = time.strftime(f"%Y-%m-%d {hourint}:%M:%S %Z%z")

    with open(f"{usernamefin}.txt", 'at') as f:
        f.write(f"{usernamefin} created account at " + current_time + "\n")
        f.close()

    messagebox.showinfo("Success!", "You have successfully signed up." + "\n" + "Your username is: " +
                        usernamefin)

    # destroys the  gui so that the user goes back to the home screen
    root.destroy()
    import main


def openLogInPage():
    root.destroy()
    time = datetime.now()
    current_time = time.strftime("%Y-%m-%d %H:%M:%S %Z%z")
    with open('logText.txt', 'at') as f:
        f.write("Anonymous User Opened Log In Page at " + current_time + "\n")
    f.close()
    import login


# the submit button is the button that is pressed when the user is done inputting data. It calls the signingin function.
submit_button = Button(root, text="Submit", command=signingin)
submit_button.grid(row=4, column=0)

login_button = Button(root, text="Login Page", command=openLogInPage)
login_button.grid(row=4, column=1)
