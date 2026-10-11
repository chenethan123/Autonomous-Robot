#for when entering the password. hashing will encrypt the password in the sql database
import hashlib

#for file paths
import os

#imports sqlite3, which will be used to create a sql database

#imports all of the required tkinter libraries
from tkinter import *
root = Tk()
from tkinter import ttk
from tkinter import messagebox
import tkinter as tk

from datetime import datetime

import sqlpage

# creates the tk gui
root.geometry()
root.geometry("510x1020")
root.title("Choose")

#function that will open up the sign in page
def openSignUpPage():
  root.destroy()
  time = datetime.now()
  current_time = time.strftime("%Y-%m-%d %H:%M:%S %Z%z")
  with open('logText.txt', 'at') as f:
    f.write("Signup page opened at " + current_time + "\n")
    f.close()
  import signup


#function that will open up the log in page
def openLogInPage():
  root.destroy()
  time = datetime.now()
  current_time = time.strftime("%Y-%m-%d %H:%M:%S %Z%z")
  with open('logText.txt', 'at') as f:
    f.write("Login page opened at " + current_time + "\n")
    f.close()
  import login

#creates a login button and sets up their location. The login button runs a function to open up the login screen.
login_button = Button(root, text="Login", command=openLogInPage)
login_button.grid(row=0,column=0)
#creates a signup button and sets up their location. The signup button runs a function to open up the signup screen.
signup_button = Button(root, text="Create Account", command=openSignUpPage)
signup_button.grid(row=1,column=0)
#creates an exit button that will destroy the gui. This will end the program.
enter_button = Button(root, text="Exit", command=root.destroy)
enter_button.grid(row=2,column=0)

# keeps the gui from disappearing/keeps it on screen
root.mainloop()
