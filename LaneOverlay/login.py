# imports the import tkinter libraries in order for creating gui
from tkinter import *
import tkinter as tk
import hashlib

root = Tk()
from tkinter import ttk
from tkinter import messagebox

# creates the tk gui
root.geometry()
root.geometry("510x1020")
root.title("Login")

from datetime import datetime

# imports the sqlite3 library in order for the database to be used
import sqlite3

# connects to the database
database = sqlite3.connect('login.db')

# creates a cursor object that allows interaction with the database
cursor = database.cursor()

# sets up the username and password as string variables
username = StringVar()
password = StringVar()

# puts entry boxes for username and password there and sets up their location
user_name = Entry(root, textvariable=username)
user_name.grid(row=0, column=0)
# the show part makes it so that the password appears as astericks
passw = Entry(root, textvariable=password, show='*')
passw.grid(row=0, column=1)

# puts labels under the entry boxes for username and password
user_name_label = Label(root, text="Enter your username.")
user_name_label.grid(row=2, column=0)
passw_label = Label(root, text="Enter your password.")
passw_label.grid(row=2, column=1)


# a function dedicated to starting the process with retrieving the inputted data from the entry boxes and database
def retrievingdata():
    # gets the input from the username entry box and password entry box
    userinput = user_name.get()
    passinput = passw.get()

    global extrauser
    extrauser = userinput

    # creates the table in case it wasn't already
    cursor.execute(''' CREATE TABLE IF NOT EXISTS logindata
       (userid     INTEGER PRIMARY KEY, 
       username TEXT,
       password TEXT,
       first_name TEXT,
       last_name TEXT)
       ''')

    # commits all edits to the database
    database.commit()

    # makes the database search for values
    cursor.execute(''' SELECT password, first_name FROM logindata WHERE username = ?''',
                   (userinput,))

    # commits this search to the database
    database.commit()

    # sets all of the data to a variable that can later be used for un-tupling the values
    retrieveddata = cursor.fetchone()

    # calls the loggingin function and sends the retrieveddata and the password inputted variables
    loggingin(retrieveddata, passinput, userinput)


# this function will focus on the actual login process, checking username and password
def loggingin(retrieveddata, passinput, userinput):
    # checks if there is data in the variable
    if retrieveddata:
        # unpacks the tuple with the password and first name
        datapassword, user_firstname = retrieveddata
        # encodes the password inputted so that it can later be compared to the encoded saved password
        passwordencodeagain = passinput.encode("utf-8")
        repassword = hashlib.sha512(passwordencodeagain).hexdigest()
        # checks if the contents of the encoded inputted password are equal to that of the password from the database
        if repassword == datapassword:
            # imports the final gui file if the password is the same as the database. the user is officially logged in.

            time = datetime.now()
            current_hour = time.strftime("%H")
            hourint = int(current_hour) - 5
            if hourint < 0:
                hourint = 24 + hourint
            current_time = time.strftime(f"%Y-%m-%d {hourint}:%M:%S %Z%z")

            openFile = open(f"{userinput}.txt", "a")

            with open(f"{userinput}.txt", 'at') as f:
                f.write(f"{userinput} logged in at " + current_time + "\n")
                f.close()

            # destroys the original GUI
            root.destroy()

            import finalgui

        # if the encoded passwords are not equal, then the user is told to try again.
        else:
            messagebox.showerror("Oops", "Incorrect Password! Please try again.")
    # if there is nothing retrieved, then the user is told to try another username.
    else:
        messagebox.showerror("Oops!", "Such user does not exist!")
        root.destroy()
        import main


# the submit button calls the retrievingdata function. It essentially submits the entry data.
submit_button = Button(root, text="Submit", command=retrievingdata)
submit_button.grid(row=4, column=0)
