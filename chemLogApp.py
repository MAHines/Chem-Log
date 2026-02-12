import streamlit as st
import pandas as pd
import os
import platform
import gspread
import time
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from oauth2client.service_account import ServiceAccountCredentials
import streamlit.components.v1 as components
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
# See README.md for more information.

# Dict to associate course number with sheet name
ALLOWED_COURSES = {'2070': 'Chem_2070', '2510': 'Chem_2510', 'Test': 'Test'}
SHEET_NAME = 'Lab Attendance, Spring 2026'

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
                st.session_state['course_num'] = course_num
                st.session_state['TA_name'] = TA_name
                
                # Use the current datetime to determine the section (e.g., Mon Afternoon)
                utc_now = datetime.now(ZoneInfo("UTC"))
                ny_time = utc_now.astimezone(ZoneInfo("America/New_York"))
                st.session_state['Start_datetime'] = ny_time
                
                formatted_datetime = ny_time.strftime('%a ') # Ex Mon
                if int(ny_time.strftime('%H')) < 12:
                    formatted_datetime += 'AM'
                else:
                    formatted_datetime += 'PM'
                section = formatted_datetime
                st.session_state['section'] = section
            
                # Format the information for the first three columns of the sheet
                st.session_state['first_cols'] = [course_num, TA_name, section]

                # Initiate a new dataframe if the TA is just logging in
                if not st.session_state['class_initiated']:
                    # Set up the dataframe to hold the students
                    column_names = ['ID', 'Time']
                    entries_df = pd.DataFrame(columns=column_names).sort_index(ascending=False)
                    st.session_state.entries_df = entries_df
            
                    st.session_state['class_initiated'] = True   
                
                st.rerun()

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
    pattern = r'^[a-zA-Z]{2,3}\d+'
    
    if re.match(pattern, s):
        return True
    else:
        return False

def submit_ID():
    """ Processes the card swipe """
    input = st.session_state.card_input
    entries_df = st.session_state['entries_df']
    st.session_state.card_input = ''
    
    # Need to make sure the TA info is "fresh"
    utc_now = datetime.now(ZoneInfo("UTC"))
    ny_time = utc_now.astimezone(ZoneInfo("America/New_York"))
    hrs_since_login = (ny_time - st.session_state['Start_datetime'])/timedelta(hours = 1)
    if hrs_since_login > 4.0:
         sign_out()
         return   
    
    # The ID number is a subset of the data on the card.
    if len(input) < 8 and check_string_is_netID(input):  # Did they enter a netID
        cornellID_number = input
    elif len(input) > 16:
        cornellID_number = input[8:15]
    else:   
        st.session_state.card_input = 'Cannot interpret input as ID or netID. Try again.'
        return(0)

    # Get current time
    formatted_datetime = curDateTimeString()

    # Update the Google sheet
    spreadsheet_entry = st.session_state['first_cols'] + [cornellID_number, formatted_datetime]
    try:
        append_row_to_google_sheet(spreadsheet_entry)
    except Exception as e:
        st.session_state.card_input = 'Write failed. Check wifi and try again.'
        st.error(f'Failed after retries (likely wifi issue): {e}')
        return(-1)

    # Archive the swipe in the dataframe
    df_entry = [cornellID_number, formatted_datetime]
    entries_df.loc[len(entries_df)] = df_entry
    entries_df = entries_df.sort_index(ascending=False, inplace = True)
    

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
    st.session_state['class_initiated'] = False
    st.session_state.entries_df = None

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
    sh = client.open(SHEET_NAME)
    sheetName = sh.worksheet(ALLOWED_COURSES[st.session_state['course_num']])    
    sheetName.append_row(spreadsheet_entry) # Actual spreadsheet entry
 
# Initialization
if 'class_initiated' not in st.session_state:
    st.session_state['class_initiated'] = False
    
# Display the logo and the welcome message
col1, col2 = st.columns([1, 1], vertical_alignment="center")
with col1:
    st.image("assets/icon.png", width=250)

with col2:
    st.html('<div style="text-align: center;font-size: 44px;font-weight: bold">Welcome to Chem Log </div>')

# with st.container(horizontal_alignment="center"): #
#     st.image("assets/icon.png", width=250)
#     st.html('<div style="text-align: center;font-size: 44px;font-weight: bold">Welcome to Chem Log </div>')

if not st.session_state['class_initiated']:
    nameOfTA_dialog()
else:
    # Display the TA info if someone is logged in
    st.write('### ' + st.session_state['TA_name'] + '\\\'s Chem ' + st.session_state['course_num'] + ' ' + st.session_state['section'] + ' Section')

# Allow the TA to log in repeatedly in case of errors
col1, col2 = st.columns(2)
with col1:
    if st.button('Update TA & Class Info'):
        nameOfTA_dialog()
with col2:
    if st.session_state['class_initiated']:
        st.button('TA Sign Out',
               key = 'sign_out',
               on_click = sign_out)
    
# Display the actual swiping input if class_initiated
if st.session_state['class_initiated']:
    st.text_input("Students must swipe in and out with their Cornell ID. Make sure the cursor is in the field below before swiping.",
                    key = 'card_input',
                    on_change = submit_ID)
    
    # Display dataframe for entries. This dataframe serves no purpose other than
    #   visual confirmation that the swipe is working
    st.dataframe(st.session_state.entries_df)
    

# Call the function to focus the input at the end of the script. This attempts to keep the cursor in the text box.
focus_text_input()
