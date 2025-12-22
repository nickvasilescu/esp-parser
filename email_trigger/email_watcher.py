#!/usr/bin/env python3
"""
IMAP IDLE email watcher for triggering automation workflows.

Watches for emails where nick@computeruse.agency is CC'd and
contains ESP or SAGE presentation URLs. Triggers the orchestrator
workflow automatically when a valid email is received.

Usage:
    export GMAIL_APP_PASSWORD="xxxx-xxxx-xxxx-xxxx"
    export AUTHORIZED_SENDER="client@example.com"
    python email_watcher.py
"""
import imaplib
import email
from email.header import decode_header
import re
import subprocess
import time
import logging
import os
import sys
from pathlib import Path

# ============================================================================
# CONFIGURATION
# ============================================================================
IMAP_SERVER = "imap.gmail.com"
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS", "nick@computeruse.agency")
APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

# Authorized senders (emails that can trigger workflows)
# Can be set via environment variable as comma-separated list, or defaults to these
DEFAULT_AUTHORIZED_SENDERS = [
    "koell@stblstrategies.com",
    "nickv@testkey.com",
]
_env_senders = os.getenv("AUTHORIZED_SENDERS", "")
AUTHORIZED_SENDERS = [s.strip().lower() for s in _env_senders.split(",") if s.strip()] if _env_senders else DEFAULT_AUTHORIZED_SENDERS

# Project path - detect if running locally or on server
if os.path.exists("/opt/promo-pipeline"):
    PROJECT_PATH = "/opt/promo-pipeline"
else:
    # Local development - use the directory containing this script's parent
    PROJECT_PATH = str(Path(__file__).parent.parent.absolute())

# URL patterns
ESP_PREFIX = "https://portal.mypromooffice.com/presentations/"
SAGE_PREFIX = "https://www.viewpresentation.com/"

# Directory for tracking processed emails
SCRIPT_DIR = Path(__file__).parent.absolute()
PROCESSED_FILE = SCRIPT_DIR / "processed_emails.txt"

# Logging setup - log to file if on server, otherwise just console
LOG_FILE = "/var/log/email-watcher.log" if os.path.exists("/var/log") else None
handlers = [logging.StreamHandler()]
if LOG_FILE:
    try:
        handlers.append(logging.FileHandler(LOG_FILE))
    except PermissionError:
        pass  # Skip file logging if no permission

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=handlers
)
logger = logging.getLogger(__name__)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def decode_email_header(header_value: str) -> str:
    """Decode email header (handles encoded subjects, names, etc.)"""
    if header_value is None:
        return ""
    decoded_parts = decode_header(header_value)
    result = ""
    for part, encoding in decoded_parts:
        if isinstance(part, bytes):
            result += part.decode(encoding or 'utf-8', errors='replace')
        else:
            result += part
    return result


def extract_email_address(header_value: str) -> str:
    """Extract email address from header like 'Name <email@example.com>'"""
    if not header_value:
        return ""
    match = re.search(r'<([^>]+)>', header_value)
    if match:
        return match.group(1).lower()
    return header_value.lower().strip()


def extract_all_emails(header_value: str) -> list:
    """Extract all email addresses from a header (handles multiple recipients)."""
    if not header_value:
        return []
    # Find all email addresses in angle brackets
    bracketed = re.findall(r'<([^>]+@[^>]+)>', header_value)
    if bracketed:
        return [e.lower() for e in bracketed]
    # Fallback: find bare email addresses
    bare = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', header_value)
    return [e.lower() for e in bare]


def is_user_in_cc(cc_header: str, target_email: str) -> bool:
    """Check if target email is in CC field."""
    if not cc_header:
        return False
    cc_lower = cc_header.lower()
    return target_email.lower() in cc_lower


def is_from_authorized_sender(from_header: str, authorized_senders: list) -> bool:
    """Check if email is from one of the authorized senders."""
    if not authorized_senders:
        logger.warning("No AUTHORIZED_SENDERS configured - accepting all senders")
        return True
    sender = extract_email_address(from_header)
    return any(auth_sender in sender for auth_sender in authorized_senders)


def extract_url(body: str) -> tuple:
    """
    Extract ESP or SAGE URL from email body.

    Returns:
        Tuple of (platform, url) or (None, None) if no valid URL found
    """
    # Look for ESP URL
    # Format: https://portal.mypromooffice.com/presentations/500183020?accessCode=b07e67d01cbd4ca2ba71934d128e1a44
    esp_match = re.search(
        r'https://portal\.mypromooffice\.com/presentations/\d+\?accessCode=[a-f0-9]+',
        body
    )
    if esp_match:
        return ('ESP', esp_match.group(0))

    # Look for SAGE URL
    # Format: https://www.viewpresentation.com/66907679185
    sage_match = re.search(
        r'https://www\.viewpresentation\.com/\d+',
        body
    )
    if sage_match:
        return ('SAGE', sage_match.group(0))

    return (None, None)


def get_email_body(msg) -> str:
    """Extract plain text body from email message."""
    body = ""

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))

            if content_type == "text/plain" and "attachment" not in content_disposition:
                try:
                    payload = part.get_payload(decode=True)
                    if payload:
                        body = payload.decode('utf-8', errors='replace')
                        break
                except Exception:
                    pass
            elif content_type == "text/html" and not body:
                try:
                    payload = part.get_payload(decode=True)
                    if payload:
                        html = payload.decode('utf-8', errors='replace')
                        # Basic HTML tag stripping
                        body = re.sub(r'<[^>]+>', ' ', html)
                except Exception:
                    pass
    else:
        try:
            payload = msg.get_payload(decode=True)
            if payload:
                body = payload.decode('utf-8', errors='replace')
        except Exception:
            pass

    return body


def trigger_workflow(platform: str, url: str, client_email: str = None) -> bool:
    """
    Trigger the orchestrator workflow.

    Args:
        platform: 'ESP' or 'SAGE'
        url: The presentation URL
        client_email: Optional client email for Zoho contact lookup

    Returns:
        True if workflow was triggered successfully, False otherwise
    """
    logger.info(f"Triggering {platform} workflow: {url}")
    if client_email:
        logger.info(f"  Client email: {client_email}")

    # Build command - use promo-parser CLI from venv
    promo_parser_cmd = os.path.join(PROJECT_PATH, "venv", "bin", "promo-parser")

    # Fallback to python + orchestrator for development if CLI not available
    if not os.path.exists(promo_parser_cmd):
        venv_python = os.path.join(PROJECT_PATH, "venv", "bin", "python3")
        python_cmd = venv_python if os.path.exists(venv_python) else "python3"
        promo_parser_cmd = None

    # Full workflow: all features enabled, verbose output, NO product limit
    # Note: URL is a positional argument, not a flag
    if promo_parser_cmd:
        cmd = [
            promo_parser_cmd,
            url,  # positional argument
            '--zoho-upload',
            '--zoho-quote',
            '--calculator',
            '--verbose'
        ]
    else:
        cmd = [
            python_cmd, '-m', 'promo_parser.pipelines.orchestrator',
            url,
            '--zoho-upload',
            '--zoho-quote',
            '--calculator',
            '--verbose'
        ]

    # Add client email for Zoho contact lookup if available
    if client_email:
        cmd.extend(['--client-email', client_email])

    try:
        # Create log file path based on timestamp
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        log_path = os.path.join(SCRIPT_DIR, f"workflow_{timestamp}.log")

        # Open log file for subprocess output
        log_file = open(log_path, 'w')

        # Run in background using nohup-style approach
        # Write to log file so we can debug any issues
        process = subprocess.Popen(
            cmd,
            cwd=PROJECT_PATH,
            stdout=log_file,
            stderr=subprocess.STDOUT,  # Redirect stderr to stdout (the log file)
            start_new_session=True,  # Detach from parent process
            env=os.environ.copy()  # Pass current environment variables
        )
        logger.info(f"Workflow started (PID: {process.pid})")
        logger.info(f"Workflow log: {log_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to trigger workflow: {e}")
        return False


# ============================================================================
# PROCESSED EMAILS TRACKING (avoid duplicates)
# ============================================================================

def load_processed_emails() -> set:
    """Load set of already processed email IDs."""
    try:
        with open(PROCESSED_FILE, 'r') as f:
            return set(line.strip() for line in f if line.strip())
    except FileNotFoundError:
        return set()


def mark_email_processed(email_id: str) -> None:
    """Mark an email as processed."""
    with open(PROCESSED_FILE, 'a') as f:
        f.write(f"{email_id}\n")


# ============================================================================
# IMAP IDLE IMPLEMENTATION
# ============================================================================

def process_new_emails(mail: imaplib.IMAP4_SSL, processed_ids: set) -> None:
    """Check for and process new emails."""
    # Search for unread emails
    status, messages = mail.search(None, 'UNSEEN')
    if status != 'OK':
        return

    email_ids = messages[0].split()

    if not email_ids:
        return

    logger.info(f"Found {len(email_ids)} unread email(s)")

    for email_id in email_ids:
        email_id_str = email_id.decode()

        # Skip if already processed
        if email_id_str in processed_ids:
            logger.debug(f"Skipping already processed email: {email_id_str}")
            continue

        # Fetch the email
        status, msg_data = mail.fetch(email_id, '(RFC822)')
        if status != 'OK':
            logger.warning(f"Failed to fetch email {email_id_str}")
            continue

        raw_email = msg_data[0][1]
        msg = email.message_from_bytes(raw_email)

        # Extract headers
        from_header = decode_email_header(msg.get('From', ''))
        cc_header = decode_email_header(msg.get('Cc', ''))
        to_header = decode_email_header(msg.get('To', ''))
        subject = decode_email_header(msg.get('Subject', ''))

        logger.info(f"New email: '{subject}' from {from_header}")

        # Check if from authorized sender
        if not is_from_authorized_sender(from_header, AUTHORIZED_SENDERS):
            logger.info(f"  Skipped: Not from authorized sender (allowed: {', '.join(AUTHORIZED_SENDERS)})")
            continue

        # Check if user is CC'd (or in To: for testing)
        is_ccd = is_user_in_cc(cc_header, EMAIL_ADDRESS)
        is_direct = EMAIL_ADDRESS.lower() in to_header.lower()

        if not is_ccd and not is_direct:
            logger.info(f"  Skipped: {EMAIL_ADDRESS} not in CC or To")
            continue

        # Extract body and look for URL
        body = get_email_body(msg)
        platform, url = extract_url(body)

        if platform and url:
            logger.info(f"  Found {platform} URL: {url}")

            # Extract client email from To: header (excluding our trigger email)
            to_emails = extract_all_emails(to_header)
            client_emails = [e for e in to_emails if EMAIL_ADDRESS.lower() not in e.lower()]
            client_email = client_emails[0] if client_emails else None

            if client_email:
                logger.info(f"  Client email: {client_email}")
            else:
                logger.info(f"  No client email found in To: header")

            if trigger_workflow(platform, url, client_email=client_email):
                mark_email_processed(email_id_str)
                processed_ids.add(email_id_str)
                logger.info(f"  Workflow triggered successfully")
            else:
                logger.error(f"  Failed to trigger workflow")
        else:
            logger.info(f"  No valid presentation URL found in email body")


def watch_inbox() -> None:
    """Main loop using IMAP IDLE."""
    processed_ids = load_processed_emails()
    logger.info(f"Loaded {len(processed_ids)} previously processed email IDs")

    while True:
        mail = None
        try:
            logger.info("Connecting to Gmail IMAP...")
            mail = imaplib.IMAP4_SSL(IMAP_SERVER)
            mail.login(EMAIL_ADDRESS, APP_PASSWORD)
            mail.select('INBOX')
            logger.info("Connected! Watching for new emails...")

            # Process any existing unread emails first
            process_new_emails(mail, processed_ids)

            # Enter IDLE mode loop
            idle_timeout = 0
            while True:
                # IMAP IDLE - wait for new mail
                # Gmail's IDLE timeout is about 10 minutes, we'll refresh at 5
                tag = mail._new_tag().decode()
                mail.send(f'{tag} IDLE\r\n'.encode())

                # Read continuation response
                response = mail.readline()
                if b'+' not in response:
                    logger.warning(f"Unexpected IDLE response: {response}")
                    mail.send(b'DONE\r\n')
                    break

                # Wait for EXISTS notification (new mail) or timeout
                mail.sock.settimeout(300)  # 5 minute timeout

                try:
                    while True:
                        response = mail.readline()

                        if b'EXISTS' in response:
                            # New email arrived!
                            logger.info("New email notification received")
                            mail.send(b'DONE\r\n')
                            # Read the tagged OK response
                            mail.readline()
                            process_new_emails(mail, processed_ids)
                            break
                        elif b'OK' in response and tag.encode() in response:
                            # IDLE completed normally
                            break
                        elif b'BYE' in response:
                            # Server closing connection
                            logger.info("Server sent BYE, reconnecting...")
                            raise ConnectionResetError("Server closed connection")

                except TimeoutError:
                    # Timeout - exit IDLE and restart it
                    logger.debug("IDLE timeout, refreshing connection...")
                    mail.send(b'DONE\r\n')
                    try:
                        mail.readline()  # Read OK response
                    except Exception:
                        pass

                    # Do a quick NOOP to keep connection alive
                    mail.noop()
                    idle_timeout += 1

                    if idle_timeout >= 6:  # ~30 minutes
                        # Reconnect to ensure fresh connection
                        logger.info("Periodic reconnection to Gmail...")
                        break

        except imaplib.IMAP4.abort as e:
            logger.warning(f"IMAP connection aborted: {e}")
        except imaplib.IMAP4.error as e:
            logger.error(f"IMAP error: {e}")
        except ConnectionResetError as e:
            logger.warning(f"Connection reset: {e}")
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
        finally:
            if mail:
                try:
                    mail.close()
                    mail.logout()
                except Exception:
                    pass

        # Reconnect after delay
        logger.info("Reconnecting in 30 seconds...")
        time.sleep(30)


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """Main entry point with configuration validation."""

    # Validate required configuration
    if not APP_PASSWORD:
        print("Error: GMAIL_APP_PASSWORD environment variable not set")
        print("")
        print("To get an app password:")
        print("1. Go to https://myaccount.google.com/apppasswords")
        print("2. Create an app password for 'Mail'")
        print("3. Set it: export GMAIL_APP_PASSWORD='xxxx-xxxx-xxxx-xxxx'")
        sys.exit(1)

    if not AUTHORIZED_SENDERS:
        print("Warning: No AUTHORIZED_SENDERS configured - will accept emails from anyone!")
        print("Set it: export AUTHORIZED_SENDERS='email1@example.com,email2@example.com'")
        print("")

    # Print configuration
    logger.info("=" * 60)
    logger.info("Email Trigger Watcher Starting")
    logger.info(f"  Email: {EMAIL_ADDRESS}")
    logger.info(f"  Authorized Senders:")
    for sender in AUTHORIZED_SENDERS:
        logger.info(f"    - {sender}")
    logger.info(f"  Project Path: {PROJECT_PATH}")
    logger.info(f"  Processed File: {PROCESSED_FILE}")
    logger.info("=" * 60)
    logger.info("")
    logger.info("Workflow command: promo-parser <url> --zoho-upload --zoho-quote --calculator --verbose")
    logger.info("  (No product limit - processes ALL products)")
    logger.info("")
    logger.info("URL patterns being watched:")
    logger.info(f"  ESP:  {ESP_PREFIX}*")
    logger.info(f"  SAGE: {SAGE_PREFIX}*")
    logger.info("")

    # Start watching
    watch_inbox()


if __name__ == '__main__':
    main()
