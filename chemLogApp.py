import streamlit as st
import pandas as pd
import os
import platform
import gspread
from datetime import datetime
from zoneinfo import ZoneInfo
from oauth2client.service_account import ServiceAccountCredentials
import streamlit.components.v1 as components

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
ALLOWED_COURSES = {'2070': 'Chem_2070', '2080': 'Chem_2080', '2510': 'Chem_2510'}

@st.dialog('Enter TA name and Course Number before proceeding', dismissible=False)
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
        if submitted:
            if not course_num in ALLOWED_COURSES:
                error_message_placeholder.error('Enter a valid course number')
            elif not TA_name:
                error_message_placeholder.error('TA name is required')
            else:
                st.session_state['course_num'] = course_num
                st.session_state['TA_name'] = TA_name
                
                # Use the current datetime to determine the section (e.g., Mon Afternoon)
                utc_now = datetime.now(ZoneInfo("UTC"))
                ny_time = utc_now.astimezone(ZoneInfo("America/New_York"))
                
                formatted_datetime = ny_time.strftime('%a ') # Ex Mon
                if int(ny_time.strftime('%H')) < 12:
                    formatted_datetime += 'Morning'
                else:
                    formatted_datetime += 'Afternoon'
                section = formatted_datetime
                st.session_state['section'] = section
            
                # Format the information for the first three columns of the sheet
                st.session_state['first_cols'] = [course_num, TA_name, section]

                # Initiate a new dataframe if the TA is just logging in
                if not st.session_state['class_initiated']:
                    # Set up the dataframe to hold the students
                    column_names = ['ID', 'Time']
                    entries_df = pd.DataFrame(columns=column_names)
                    st.session_state.entries_df = entries_df
            
                    st.session_state['class_initiated'] = True   
                
                st.rerun()

def curDateTimeString():
    
    utc_now = datetime.now(ZoneInfo("UTC"))
    ny_time = utc_now.astimezone(ZoneInfo("America/New_York"))
    
    return(ny_time.strftime("%a, %d %b %y, %I:%M %p")) # Ex Sat_Dec_20_2025

def submit_ID():
    """ Processes the card swipe """
    input = st.session_state.card_input
    st.session_state.card_input = ''
    
    # The ID number is a subset of the data on the card.
    cornellID_number = input[8:15]
    
    # Get current time
    formatted_datetime = curDateTimeString()
    
    # Archive the swipe in the dataframe and the spreadsheet
    df_entry = [cornellID_number, formatted_datetime]
    spreadsheet_entry = st.session_state['first_cols'] + [cornellID_number, formatted_datetime]
    
    st.session_state.entries_df.loc[len( st.session_state.entries_df)] = df_entry
    st.session_state['worksheet'].append_row(spreadsheet_entry) # Actual spreadsheet entry

# Function to inject JavaScript for focusing the input
def focus_text_input():
    # This script searches for text inputs and focuses on the last one
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

# Define the scope of the Google Sheet
scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/spreadsheets',
         "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]

# Process credentials to the account
google_service_account_info = st.secrets['google_service_account']
creds = ServiceAccountCredentials.from_json_keyfile_dict(google_service_account_info, scope)
client = gspread.authorize(creds)

# This tries to remove the large amount of white space at the top of the page
st.markdown("""
        <style>
               .block-container {
                    padding-top: 1rem;
                    padding-bottom: 0rem;
                    padding-left: 5rem;
                    padding-right: 5rem;
                }
        </style>
        """, unsafe_allow_html=True)

# Initialization
if 'class_initiated' not in st.session_state:
    st.session_state['class_initiated'] = False
else:    
    # Open the appropriate worksheet
    sh = client.open('Card Swipe Shared Sheet')
    
    # … and the appropriate sheet
    st.session_state['worksheet'] = sh.worksheet(ALLOWED_COURSES[st.session_state['course_num']])
    
# Display the logo and the welcome message
with st.container(horizontal_alignment="center"): #
    st.image("assets/icon.png", width=250)
    st.title('Welcome to Chem Log')

if not st.session_state['class_initiated']:
    nameOfTA_dialog()
else:
    # Display the TA info if someone is logged in
    st.write('### ' + st.session_state['TA_name'] + '\\\'s Chem ' + st.session_state['course_num'] + ' ' + st.session_state['section'] + ' Section')


# Allow the TA to log in repeatedly in case of errors
if st.button('Update Class Info'):
    nameOfTA_dialog()
    
# Display the actual swiping input if class_initiated
if st.session_state['class_initiated']:
    st.text_input("Students must swipe their Cornell ID. Make sure the cursor is in the field below before swiping.",
                    key = 'card_input',
                    on_change = submit_ID)
    
    # Display dataframe for entries. This dataframe serves no purpose other than
    #   visual confirmation that the swipe is working
    st.dataframe(st.session_state.entries_df)
    
    # Enable log out
    st.button('TA Sign Out',
               key = 'sign_out',
               on_click = sign_out)

# Call the function to focus the input at the end of the script. This attempts to keep the cursor in the text box.
focus_text_input()
