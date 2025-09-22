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


def get_contact_number(name: str) -> str | None:
    """
    Look up a contact's phone number from the macOS Contacts app.
    Prefers 'mobile' number if available.
    """
    applescript = f'''
    tell application "Contacts"
        set thePeople to every person whose name contains "{name}"
        if (count of thePeople) > 0 then
            set thePerson to item 1 of thePeople
            if (count of phones of thePerson) > 0 then
                repeat with ph in phones of thePerson
                    if label of ph contains "mobile" then
                        return value of ph
                    end if
                end repeat
                -- fallback: just return first phone
                return value of first phone of thePerson
            end if
        end if
        return ""
    end tell
    '''
    result = subprocess.run(
        ["osascript", "-e", applescript],
        capture_output=True,
        text=True
    )
    number = result.stdout.strip()
    return number if number else None


@function_tool()
async def send_text_message(recipient: str, message: str):
    """
    Sends a message through the macOS Messages app.
    recipient: either a name in contacts or a phone number string
    message: message text
    """
    try:
        recipient = recipient.strip()

        # Try to resolve via Contacts app
        recipient_number = get_contact_number(recipient)

        # If not found in Contacts, assume raw phone number
        if not recipient_number:
            recipient_number = recipient

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
            return f"Message sent to {recipient} ({recipient_number})."
        else:
            return f"Failed to send message to {recipient}: {result.stderr or result.stdout}"

    except Exception as e:
        return f"Error: {str(e)}"
    
def get_contact_email(name: str) -> str | None:
    """
    Look up a contact's email address from the macOS Contacts app.
    Prefers the first email, or None if not found.
    """
    applescript = f'''
    tell application "Contacts"
        set thePeople to every person whose name contains "{name}"
        if (count of thePeople) > 0 then
            set thePerson to item 1 of thePeople
            if (count of emails of thePerson) > 0 then
                return value of first email of thePerson
            end if
        end if
        return ""
    end tell
    '''
    result = subprocess.run(
        ["osascript", "-e", applescript],
        capture_output=True,
        text=True
    )
    email = result.stdout.strip()
    return email if email else None
    
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
        to_email: Recipient email address or contact name
        subject: Email subject line
        message: Email body content
        cc_email: Optional CC email address or contact name
    """
    try:
        # Resolve contact names to actual emails
        resolved_to = get_contact_email(to_email) or to_email
        if "@" not in resolved_to:
            return f"I'm sorry sir but unfortunately '{to_email}' doesn’t have an email provided."
        
        resolved_cc = None
        if cc_email:
            resolved_cc = get_contact_email(cc_email) or cc_email
            if "@" not in resolved_cc:
                return f"I'm sorry sir but unfortunately '{cc_email}' doesn’t have an email provided."

        # Gmail SMTP configuration
        smtp_server = "smtp.gmail.com"
        smtp_port = 587
        
        gmail_user = os.getenv("GMAIL_USER")
        gmail_password = os.getenv("GMAIL_APP_PASSWORD")
        
        if not gmail_user or not gmail_password:
            logging.error("Gmail credentials not found in environment variables")
            return "Email sending failed: Gmail credentials not configured."
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = gmail_user
        msg['To'] = resolved_to
        msg['Subject'] = subject
        
        recipients = [resolved_to]
        if resolved_cc:
            msg['Cc'] = resolved_cc
            recipients.append(resolved_cc)
        
        msg.attach(MIMEText(message, 'plain'))
        
        # Connect to Gmail SMTP
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(gmail_user, gmail_password)
        server.sendmail(gmail_user, recipients, msg.as_string())
        server.quit()
        
        return f"📧 Email sent successfully to {resolved_to}" + (f" (cc: {resolved_cc})" if resolved_cc else "")
        
    except smtplib.SMTPAuthenticationError:
        return "❌ Email sending failed: Authentication error. Please check your Gmail credentials."
    except smtplib.SMTPException as e:
        return f"❌ Email sending failed: SMTP error - {str(e)}"
    except Exception as e:
        return f"❌ An error occurred while sending email: {str(e)}"


@function_tool()
async def call_contact(contact: str) -> str:
    """
    Calls a contact using macOS (FaceTime/Phone).
    
    Args:
        contact (str): Name of the contact (e.g., "Dad", "Mom") or raw number.
        
    Returns:
        str: Success or error message
    """
    try:
        contact = contact.strip()

        # Try resolving via Contacts
        number = get_contact_number(contact)

        # If not found in Contacts, assume raw phone number
        if not number:
            number = contact

        # Use FaceTime (macOS doesn't have a standalone Phone app)
        subprocess.run(["open", f"tel://{number}"], check=True)

        return f"📞 Calling {contact} ({number}) now..."
    except subprocess.CalledProcessError as e:
        return f"❌ Failed to call {contact}: {e}"
    except Exception as e:
        return f"❌ Error: {e}"