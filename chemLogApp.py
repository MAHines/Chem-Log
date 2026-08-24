import streamlit as st
import pandas as pd
import os
import platform
import gspread
import time
import re
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo
from oauth2client.service_account import ServiceAccountCredentials
import streamlit.components.v1 as components
from streamlit import session_state as ss
from tenacity import retry, stop_after_attempt, wait_fixed

# This is a severless streamlit app based on stlite/desktop (https://stlite.net).
# The package runs entirely in a browser and does not require installation of Python, Pandas, etc.
# Instead the package runs in Pyodide.
# 
# The app stores its data in multiple sheets within a Google worksheet. The API is described
# at https://developers.google.com/workspace/sheets/api/quickstart/python) and 
# https://docs.streamlit.io/develop/tutorials/databases/private-gsheet. Access is controlled by
# a secrets file that is not archived (for obvious reasons) but is located at ./.streamlit/secrets.toml.
#
# New sheets need to be shared with pythonsheets@python-sheets-access-482313.iam.gserviceaccount.com
# 
# See README.md for more information.

# Dict to associate course number with sheet name
ALLOWED_COURSES = {'2070': 'Chem_2070', '2080': 'Chem_2080', '2510': 'Chem_2510', 'Test': 'Chem_Test'}

def currentTerm():
    """ Guesses the current semester based on today's date, e.g. Fall 2026. From microscope/downloadResults.py"""
    today = date.today()
    springEnd = datetime.strptime('May 20 2025', '%b %d %Y').date().replace(year=today.year)
    summerEnd = datetime.strptime('Aug 20 2025', '%b %d %Y').date().replace(year=today.year)
    term = 'Spring' if today < springEnd else ('Summer' if today < summerEnd else 'Fall')
    curTerm = term + ' ' + str(today.year)
    return curTerm

@st.dialog('TA must sign in before you swipe', dismissible=False)
def nameOfTA_dialog():
    """ Use a modal dialog to ask the user for a name for the analysis. This will appear at
    the top of the main page if no one has logged in."""

    with st.form('TA_info', clear_on_submit = False):
        # Use a form to get TA name and course number.
        TA_name = st.text_input('TA name', key="dialog_name")
        course_num = st.text_input('Course number', key="dialog_course_num")
        
        # A placeholder for validation error messages
        error_message_placeholder = st.empty()
        
        # Submit button for the form
        submitted = st.form_submit_button("Submit")

        # Perform very simple validation. This should be better.
        TA_name_word_count = len(TA_name.split())
        if submitted:
            if course_num not in ALLOWED_COURSES:
                error_message_placeholder.error('Enter a valid course number')
            elif not TA_name:
                error_message_placeholder.error('TA name is required')
            elif TA_name_word_count > 1:
                 error_message_placeholder.error('TA name should be one word (e.g., CynthiaK)')
            else:
                ss['course_num'] = course_num
                ss['TA_name'] = TA_name
                
                # Use the current datetime to determine the section (e.g., Mon Afternoon)
                utc_now = datetime.now(ZoneInfo("UTC"))
                ny_time = utc_now.astimezone(ZoneInfo("America/New_York"))
                ss['Start_datetime'] = ny_time
                
                formatted_datetime = ny_time.strftime('%a ') # Ex Mon
                if int(ny_time.strftime('%H')) < 12:
                    formatted_datetime += 'AM'
                else:
                    formatted_datetime += 'PM'
                section = formatted_datetime
                ss['section'] = section
            
                # Format the information for the first three columns of the sheet
                ss['first_cols'] = [course_num, TA_name, section]

                # Read the roster
                error = read_Alfred_roster()
                if error < 0:
                    error_message_placeholder.error('Roster not read. Check wifi!')
                    ss['class_initiated'] = False
                    return
                
                # Initiate a new dataframe if the TA is just logging in
                if not ss['class_initiated']:
                    # Set up the dataframe to hold the students
                    column_names = ['ID', 'Time']
                    entries_df = pd.DataFrame(columns=column_names).sort_index(ascending=False)
                    ss.entries_df = entries_df
            
                    ss['class_initiated'] = True   
                
                st.rerun()

def read_Alfred_roster():
    ss['rosterSheetName'] = 'Chem_' + ss['course_num'] + '_Roster'
    
    error, roster_df = read_roster_sheet()
    if error < 0:
        return -1

    ss['roster_df'] = roster_df
    ss['roster_read'] = True
    return 0

def read_roster_sheet():

    # Now open the sheet for the roster and read
    try:
        data = read_google_sheet_with_retry(ss['rosterSheetName'], 'roster')
    except Exception as e:
        st.error(f'Failed after retries (likely wifi issue):: {e}')
        return -1, None
    
    headers = data.pop(0)
    roster_df = pd.DataFrame(data, columns = headers)
    roster_df.drop_duplicates(inplace = True)
        
    return 0, roster_df

@retry(
    stop=stop_after_attempt(5), # Stop after a maximum of 5 attempts
    wait=wait_fixed(1) 
)
def read_google_sheet_with_retry(sheetName, msg):   # Open Sheet, then read entire sheet with sheetName
    
    message = f'Reading {msg} Google sheet'
    alert = st.warning(message)
    scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/spreadsheets',
             "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
    google_service_account_info = st.secrets['google_service_account']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(google_service_account_info, scope)
    client = gspread.authorize(creds)
    sh = client.open(ss['workbook'])
    
    # Open the appropriate sheet and read it
    data = sh.worksheet(sheetName).get_all_values()
    alert.empty()
    return data

def curDateTimeString():
    
    utc_now = datetime.now(ZoneInfo("UTC"))
    ny_time = utc_now.astimezone(ZoneInfo("America/New_York"))
    
    return(ny_time.strftime("%a, %d %b %y, %I:%M %p")) # Ex Sat_Dec_20_2025

def check_string_is_netID(s):
    """
    Checks if a string starts with 2 or 3 alphanumeric characters 
    (a-z, A-Z) followed by an integer.
    """
    # The regex pattern is:
    # ^      - start of the string
    # [a-zA-Z]{2,3} - exactly 2 or 3 alphanumeric characters
    # \d+    - one or more digits (integer part)
    # $ no more characters
    pattern = r'^[a-zA-Z]{2,3}\d+$'
    
    if re.match(pattern, s):
        return True
    else:
        return False

def validate_entry(input):

    # The ID number is a subset of the data on the card.
    substring = str(input[8:15])
    roster_df = ss['roster_df']
    if len(input) < 8 and check_string_is_netID(input):  # Did they enter a netID
        netID = input
        if netID in roster_df['netID'].values:
            return True, netID
        else:
            return False, None
    elif substring.isdigit() and len(substring) == 7:
        cornellID_number = substring
        if cornellID_number in roster_df['ID'].values:
            return True, cornellID_number
        else:
            return False, None
    else:
        return False, None 

def submit_ID():
    """ Processes the card swipe """
    input = ss.card_input
    entries_df = ss['entries_df']
    ss.card_input = ''
    
    # Need to make sure the TA info is "fresh"
    utc_now = datetime.now(ZoneInfo("UTC"))
    ny_time = utc_now.astimezone(ZoneInfo("America/New_York"))
    hrs_since_login = (ny_time - ss['Start_datetime'])/timedelta(hours = 1)
    if hrs_since_login > 4.0:
         sign_out()
         return   
    
    in_class, validated_data = validate_entry(input)
    if not in_class:  # Did they enter a netID
        ss['error_message'] ='### :red[Error! Student not in class. Try again.]'
        return(0)

    # Get current time
    formatted_datetime = curDateTimeString()

    # Update the Google sheet
    spreadsheet_entry = ss['first_cols'] + [validated_data, formatted_datetime]
    try:
        append_row_to_google_sheet(spreadsheet_entry)
    except Exception as e:
        ss.card_input = 'Write failed. Check wifi and try again.'
        st.error(f'Failed after retries (likely wifi issue): {e}')
        return(-1)

    # Archive the swipe in the dataframe
    df_entry = [validated_data, formatted_datetime]
    entries_df.loc[len(entries_df)] = df_entry
    entries_df = entries_df.sort_index(ascending=False, inplace = True)

    ss['error_message'] = ''
    

# Function to inject JavaScript for focusing the input
def focus_text_input():
    """ Searches for text inputs and focuses on the last one """ 
    js_script = """
    <script>
        var input = window.parent.document.querySelectorAll("input[type=text]");
        for (var i = 0; i < input.length; ++i) {
            input[i].focus();
        }
    </script>
    """
    components.html(js_script, height=0, width=0)

def sign_out():
    """ Signs out current TA """
    ss['class_initiated'] = False
    ss.entries_df = None

@retry(
    stop=stop_after_attempt(5), # Stop after a maximum of 5 attempts
    wait=wait_fixed(1) 
)
def append_row_to_google_sheet(spreadsheet_entry):
    
    scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/spreadsheets',
             "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
    google_service_account_info = st.secrets['google_service_account']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(google_service_account_info, scope)
    client = gspread.authorize(creds)
    sh = client.open(ss['workbook'])
    sheetName = sh.worksheet(ALLOWED_COURSES[ss['course_num']]) 
    sheetName.append_row(spreadsheet_entry) # Actual spreadsheet entry
 
# Initialization
if 'class_initiated' not in ss:
    ss['class_initiated'] = False
if 'error_message' not in ss:
    ss['error_message'] = ''
if 'workbook' not in ss:
    ss['workbook'] = 'Lab Attendance, ' + currentTerm() # Formerly called SHEET_NAME

# Display the logo and the welcome message
col1, col2 = st.columns([1, 1], vertical_alignment="center")
with col1:
    st.image("assets/icon.png", width=250)

with col2:
    st.html('<div style="text-align: center;font-size: 44px;font-weight: bold">Welcome to Chem Log <span style="font-size:'
    ' 14px;">v2</span></div>')

# with st.container(horizontal_alignment="center"): #
#     st.image("assets/icon.png", width=250)
#     st.html('<div style="text-align: center;font-size: 44px;font-weight: bold">Welcome to Chem Log </div>')

if not ss['class_initiated']:
    nameOfTA_dialog()
else:
    # Display the TA info if someone is logged in
    st.write('### ' + ss['TA_name'] + '\\\'s Chem ' + ss['course_num'] + ' ' + ss['section'] + ' Section')

# Allow the TA to log in repeatedly in case of errors
col1, col2 = st.columns(2)
with col1:
    if st.button('Update TA & Class Info'):
        nameOfTA_dialog()
with col2:
    if ss['class_initiated']:
        st.button('TA Sign Out',
               key = 'sign_out',
               on_click = sign_out)
    
with st.container(border = False):
    st.write(ss['error_message'])

# Display the actual swiping input if class_initiated
if ss['class_initiated']:
    ss['placeholder'] = st.container()
    st.text_input("Students must swipe in and out with their Cornell ID. Make sure the cursor is in the field below before swiping.",
                    key = 'card_input',
                    on_change = submit_ID)
    
    # Display dataframe for entries. This dataframe serves no purpose other than
    #   visual confirmation that the swipe is working
    st.dataframe(ss.entries_df)
    

# Call the function to focus the input at the end of the script. This attempts to keep the cursor in the text box.
focus_text_input()
