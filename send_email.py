import smtplib
import pandas as pd
import time
from datetime import datetime

def read_emails_from_excel(file_path, sheet_name=0, email_column='Email_Address'):
    """
    Read email addresses from an Excel file
    
    Parameters:
    file_path (str): Path to the Excel file
    sheet_name (str/int): Name or index of the sheet to read (default: first sheet)
    email_column (str): Name of the column containing email addresses
    
    Returns:
    list: List of email addresses
    """
    try:
        # Read the Excel file
        df = pd.read_excel(file_path, sheet_name=sheet_name)
        
        # Check if the email column exists
        if email_column not in df.columns:
            raise ValueError(f"Column '{email_column}' not found in the Excel file")
        
        # Extract email addresses and remove any NaN values
        emails = df[email_column].dropna().tolist()
        
        # Remove duplicates and return
        return list(set(emails))
    
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.")
        return []
    except Exception as e:
        print(f"Error reading Excel file: {e}")
        return []

def main():
    # Specify the path to your Excel file
    excel_file = "/home/kelechukwu/Documents/Business_outreach.xlsx"
    
    # Read email addresses
    email_list = read_emails_from_excel(excel_file)
    
    # Limit to first 20 emails for testing
    email_list = email_list[:20]
    
    print(f"Found {len(email_list)} email addresses. Starting to send...")
    
    # Mailtrap credentials
    MAILTRAP_HOST = "sandbox.smtp.mailtrap.io"
    MAILTRAP_PORT = 2525
    MAILTRAP_USERNAME = "c3ba932e1864a1"
    MAILTRAP_PASSWORD = "2ebaa6023c9195"
    
    sender = "favourkaycee23@gmail.com"
    
    successful_sends = 0
    failed_sends = 0
    
    for i, receiver in enumerate(email_list):
        try:
            message = f"""\
Subject: Hi Mailtrap Test
To: {receiver}
From: {sender}

This is a test e-mail message sent at {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}."""

            with smtplib.SMTP(MAILTRAP_HOST, MAILTRAP_PORT) as server:
                server.starttls()
                server.login(MAILTRAP_USERNAME, MAILTRAP_PASSWORD)
                server.sendmail(sender, receiver, message)
            
            successful_sends += 1
            print(f"✓ Sent email {i+1}/{len(email_list)} to: {receiver}")
            
            # Add delay between emails (2-5 seconds to avoid rate limiting)
            time.sleep(3)
            
        except smtplib.SMTPResponseException as e:
            error_code = e.smtp_code
            error_message = e.smtp_error
            print(f"✗ SMTP Error ({error_code}) for {receiver}: {error_message}")
            failed_sends += 1
            
            # If we get a rate limit error, wait longer
            if error_code in [421, 450, 452]:
                print("Rate limit detected, waiting 60 seconds...")
                time.sleep(60)
                
        except Exception as e:
            print(f"✗ Error sending to {receiver}: {str(e)}")
            failed_sends += 1
            time.sleep(5)  # Wait a bit longer on generic errors
    
    print(f"\nSummary: {successful_sends} successful, {failed_sends} failed")

if __name__ == "__main__":
    main()