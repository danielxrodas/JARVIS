import subprocess
from dotenv import load_dotenv
from livekit.agents import function_tool
import logging
from livekit.agents import function_tool, RunContext
import os
import smtplib
from email.mime.multipart import MIMEMultipart  
from email.mime.text import MIMEText
from typing import Optional
from livekit.agents import function_tool, RunContext
import subprocess
from typing import Optional


load_dotenv()

contacts = {
    "dad": os.getenv("DAD"),
    "mom": os.getenv("MOM"),
    "david": os.getenv("DAVID"),
    "myself": os.getenv("MYSELF"),
}


@function_tool()
async def send_text_message(recipient: str, message: str, contacts_dict: dict = contacts):
    """
    Sends a message through the macOS Messages app.
    recipient: either a name in contacts or a phone number string
    message: message text
    """
    try:
        recipient = recipient.strip().lower()
        recipient_number = contacts_dict.get(recipient, recipient)

        applescript = f'''
        tell application "Messages"
            set targetBuddy to "{recipient_number}"
            set iMessageService to 1st service whose service type = iMessage
            try
                send "{message}" to buddy targetBuddy of iMessageService
            on error
                set smsService to 1st service whose service type = SMS
                send "{message}" to buddy targetBuddy of smsService
            end try
        end tell
        '''

        result = subprocess.run(
            ["osascript", "-e", applescript],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            return f"Message sent to {recipient}."
        else:
            return f"Failed to send message to {recipient}: {result.stderr or result.stdout}"

    except Exception as e:
        return f"Error: {str(e)}"
    
    
@function_tool()
async def send_email(
    context: RunContext,  # type: ignore
    to_email: str,
    subject: str,
    message: str,
    cc_email: Optional[str] = None
) -> str:
    """
    Send an email through Gmail.
    
    Args:
        to_email: Recipient email address
        subject: Email subject line
        message: Email body content
        cc_email: Optional CC email address
    """
    try:
        # Gmail SMTP configuration
        smtp_server = "smtp.gmail.com"
        smtp_port = 587
        
        # Get credentials from environment variables
        gmail_user = os.getenv("GMAIL_USER")
        gmail_password = os.getenv("GMAIL_APP_PASSWORD")  # Use App Password, not regular password
        
        if not gmail_user or not gmail_password:
            logging.error("Gmail credentials not found in environment variables")
            return "Email sending failed: Gmail credentials not configured."
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = gmail_user
        msg['To'] = to_email
        msg['Subject'] = subject
        
        # Add CC if provided
        recipients = [to_email]
        if cc_email:
            msg['Cc'] = cc_email
            recipients.append(cc_email)
        
        # Attach message body
        msg.attach(MIMEText(message, 'plain'))
        
        # Connect to Gmail SMTP server
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()  # Enable TLS encryption
        server.login(gmail_user, gmail_password)
        
        # Send email
        text = msg.as_string()
        server.sendmail(gmail_user, recipients, text)
        server.quit()
        
        logging.info(f"Email sent successfully to {to_email}")
        return f"Email sent successfully to {to_email}"
        
    except smtplib.SMTPAuthenticationError:
        logging.error("Gmail authentication failed")
        return "Email sending failed: Authentication error. Please check your Gmail credentials."
    except smtplib.SMTPException as e:
        logging.error(f"SMTP error occurred: {e}")
        return f"Email sending failed: SMTP error - {str(e)}"
    except Exception as e:
        logging.error(f"Error sending email: {e}")
        return f"An error occurred while sending email: {str(e)}"
    

CONTACTS = {
    "dad": os.getenv("DAD"),
    "mom": os.getenv("MOM"),
    "david": os.getenv("DAVID")
}

@function_tool
async def call_contact(contact: str) -> str:
    """
    Calls a contact using FaceTime via URL (macOS).
    
    Args:
        contact (str): Name of the contact (e.g., "dad", "mom").
        
    Returns:
        str: Success or error message
    """
    contact_key = contact.strip().lower()
    contact_info = CONTACTS.get(contact_key)

    if not contact_info:
        return f"❌ Contact '{contact}' not found in your contacts."

    facetime_url = f"facetime://{contact_info}"

    try:
        subprocess.run(["open", facetime_url], check=True)
        return f"📞 Calling {contact_key} ({contact_info}) now..."
    except subprocess.CalledProcessError as e:
        return f"❌ Failed to call {contact_key}: {e}"