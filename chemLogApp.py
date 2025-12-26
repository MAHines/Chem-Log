import streamlit as st
import pandas as pd
import os
import platform
import gspread
from datetime import datetime
from zoneinfo import ZoneInfo
from oauth2client.service_account import ServiceAccountCredentials
import streamlit.components.v1 as components

ALLOWED_COURSES = ['2070', '2080', '2510']

@st.dialog('Enter TA name and Course Number before proceeding', dismissible=False)
def nameOfTA_dialog():
    """ Use a modal dialog to ask the user for a name for the analysis. This will appear at the top of the main page"""

    with st.form('TA_info', clear_on_submit = False):
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
                
                utc_now = datetime.now(ZoneInfo("UTC"))
                ny_time = utc_now.astimezone(ZoneInfo("America/New_York"))
                
                formatted_datetime = ny_time.strftime('%a ') # Ex Mon
                if int(ny_time.strftime('%H')) < 12:
                    formatted_datetime += 'Morning'
                else:
                    formatted_datetime += 'Afternoon'
                section = formatted_datetime
                st.session_state['section'] = section
            
                st.session_state['first_cols'] = [course_num, TA_name, section]

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
    input = st.session_state.card_input
    st.session_state.card_input = ''
    
    cornellID_number = input[8:15]
    formatted_datetime = curDateTimeString()
    
    df_entry = [cornellID_number, formatted_datetime]
    spreadsheet_entry = st.session_state['first_cols'] + [cornellID_number, formatted_datetime]
    
    st.session_state.entries_df.loc[len( st.session_state.entries_df)] = df_entry
    st.session_state['worksheet'].append_row(spreadsheet_entry)

# Function to inject JavaScript for focusing the input
def focus_text_input():
    # This script searches for text inputs and focuses the first one
    js_script = """
    <script>
        var input = window.parent.document.querySelectorAll("input[type=text]");
        input[0].focus()
        }
    </script>
    """
    components.html(js_script, height=0, width=0)

def sign_out():
    st.session_state['class_initiated'] = False
    st.session_state.entries_df = None

# Define the scope
scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/spreadsheets',
         "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]

# Add your credentials to the account
google_service_account_info = st.secrets['google_service_account']
creds = ServiceAccountCredentials.from_json_keyfile_dict(google_service_account_info, scope)
client = gspread.authorize(creds)

# Initialization
if 'class_initiated' not in st.session_state:
    st.session_state['class_initiated'] = False
else:    
    # Open the appropriate sheet
    sh = client.open('Card Swipe Shared Sheet')
    
    match st.session_state['course_num']:
        case '2070':
            worksheet = sh.worksheet('Chem_2070')
        case '2080':
            worksheet = sh.worksheet('Chem_2080')
        case '2510':
            worksheet = sh.worksheet('Chem_2510')
        case _:
            worksheet = sh.worksheet('Sheet1')
            print('Sheet1')
    st.session_state['worksheet'] = worksheet
    
# Add this at the beginning of your script
with st.container(horizontal_alignment="center"): #
    st.image("./assets/icon.png", width=250)
    st.title('Welcome to Chem Log')

if not st.session_state['class_initiated']:
    nameOfTA_dialog()
else:
    st.write('### ' + st.session_state['TA_name'] + '\\\'s Chem ' + st.session_state['course_num'] + ' ' + st.session_state['section'] + ' Section')


if st.button('Update Class Info'):
    nameOfTA_dialog()
    
if st.session_state['class_initiated']:
    st.text_input("Students must swipe their Cornell ID. Make sure the cursor is in the field below before swiping.",
                    key = 'card_input',
                    on_change = submit_ID)
    
    # Display database for entries
    st.dataframe(st.session_state.entries_df)
    
    # Enable log out
    st.button('TA Sign Out',
               key = 'sign_out',
               on_click = sign_out)

# Call the function to focus the input at the end of the script. This attempts to keep the cursor in the text box.
focus_text_input()
