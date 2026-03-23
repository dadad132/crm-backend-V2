"""
Email-to-Ticket Service V2
IMAP-based email processing, uses database settings, keeps emails on server
"""

import asyncio
import imaplib
import email
import uuid
from email.header import decode_header
from email.utils import parseaddr
from pathlib import Path
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Tuple

# Set default IMAP socket timeout to prevent hanging connections
IMAP_TIMEOUT = 60  # seconds

# Lazy import helper for system logger (avoids circular imports)
def _syslog(level, source, message, details=None, workspace_id=None):
    try:
        from app.core.system_logger import log_fire_and_forget
        log_fire_and_forget(level, 'email', source, message, details, workspace_id)
    except Exception:
        pass
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.ticket import Ticket, TicketHistory, TicketComment, TicketAttachment
from app.models.notification import Notification
from app.models.email_settings import EmailSettings
from app.models.processed_mail import ProcessedMail
from app.models.project import Project

# Upload directory for email attachments (same as web form uploads)
UPLOAD_DIR = Path(__file__).resolve().parents[1] / 'uploads' / 'tickets'

# Max attachment size: 10MB (same as web form)
MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024

# Setup logger
logger = logging.getLogger(__name__)

# Timezone offset (UTC+2 for South Africa)
LOCAL_TZ_OFFSET = timedelta(hours=2)



def get_local_time() -> datetime:
    """Get current time in local timezone (UTC+2)"""
    return datetime.now(timezone(LOCAL_TZ_OFFSET))


def extract_email_attachments(msg) -> List[dict]:
    """Extract attachments from an email.message.Message object.
    
    Returns a list of dicts with: filename, content, content_type, size
    Skips inline images and oversized files.
    """
    attachments = []
    
    if not msg.is_multipart():
        return attachments
    
    for part in msg.walk():
        # Skip multipart containers
        if part.get_content_maintype() == 'multipart':
            continue
        
        # Check if this part is an attachment
        content_disposition = str(part.get('Content-Disposition', ''))
        filename = part.get_filename()
        
        # Also check for MIME-encoded filenames
        if filename and '=?' in filename:
            decoded_parts = decode_header(filename)
            filename = ''
            for fpart, charset in decoded_parts:
                if isinstance(fpart, bytes):
                    filename += fpart.decode(charset or 'utf-8', errors='replace')
                else:
                    filename += fpart
        
        # Skip parts that are not attachments (no filename and no attachment disposition)
        if not filename and 'attachment' not in content_disposition.lower():
            continue
        
        # Skip inline images without filenames (embedded logos etc.)
        if not filename and 'inline' in content_disposition.lower():
            continue
        
        # Generate a filename if none provided
        if not filename:
            ext = part.get_content_type().split('/')[-1] if part.get_content_type() else 'bin'
            filename = f'attachment.{ext}'
        
        try:
            content = part.get_payload(decode=True)
            if not content:
                continue
            
            # Skip oversized attachments
            if len(content) > MAX_ATTACHMENT_SIZE:
                print(f"[Email Attachment] Skipping '{filename}' - too large ({len(content)} bytes, max {MAX_ATTACHMENT_SIZE})")
                _syslog('WARNING', 'IMAP', 'Attachment skipped - oversized', f'File={filename} | Size={len(content)} | Max={MAX_ATTACHMENT_SIZE}')
                continue
            
            content_type = part.get_content_type() or 'application/octet-stream'
            
            attachments.append({
                'filename': filename,
                'content': content,
                'content_type': content_type,
                'size': len(content)
            })
            print(f"[Email Attachment] Found: '{filename}' ({content_type}, {len(content)} bytes)")
        except Exception as e:
            print(f"[Email Attachment] Error extracting '{filename}': {e}")
            _syslog('ERROR', 'IMAP', f'Attachment extraction failed: {filename}', str(e)[:200])
            continue
    
    return attachments


async def save_email_attachments(
    db: AsyncSession,
    ticket_id: int,
    attachments: List[dict],
    comment_id: Optional[int] = None
) -> List[TicketAttachment]:
    """Save extracted email attachments to disk and create DB records.
    
    Args:
        db: Database session
        ticket_id: Ticket to attach files to
        attachments: List of dicts from extract_email_attachments()
        comment_id: Optional comment ID if attachments go with a reply comment
    
    Returns:
        List of created TicketAttachment records
    """
    if not attachments:
        return []
    
    # Ensure upload directory exists
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    
    saved = []
    for att in attachments:
        try:
            # Generate unique filename (same pattern as web form uploads)
            original_name = att['filename']
            ext = Path(original_name).suffix or '.bin'
            unique_filename = f"{uuid.uuid4()}{ext}"
            file_path = UPLOAD_DIR / unique_filename
            relative_path = f"app/uploads/tickets/{unique_filename}"
            
            # Write file to disk
            file_path.write_bytes(att['content'])
            
            # Create DB record
            attachment = TicketAttachment(
                ticket_id=ticket_id,
                comment_id=comment_id,
                filename=original_name,
                file_path=relative_path,
                file_size=att['size'],
                mime_type=att['content_type'],
                uploaded_by_id=None  # Guest upload from email
            )
            db.add(attachment)
            saved.append(attachment)
            print(f"[Email Attachment] Saved: '{original_name}' -> {relative_path}")
        except Exception as e:
            print(f"[Email Attachment] Error saving '{att.get('filename', '?')}': {e}")
            _syslog('ERROR', 'IMAP', f'Attachment save error: {att.get("filename", "?")}', str(e)[:200])
            continue
    
    if saved:
        await db.flush()  # Flush to assign IDs
        print(f"[Email Attachment] Total saved: {len(saved)} attachment(s) for ticket {ticket_id}")
    
    return saved


def is_support_query(subject: str, body: str, sender_email: str) -> bool:
    """
    Analyze if an email looks like a support query.
    Used for filtering spam/junk folder emails.
    
    Returns True if the email appears to be a legitimate support request.
    """
    content = (subject + ' ' + body).lower()
    sender = sender_email.lower()
    
    # Keywords that indicate a support query
    support_keywords = [
        'help', 'support', 'issue', 'problem', 'error', 'broken', 'not working',
        'urgent', 'please', 'assist', 'request', 'ticket', 'query', 'question',
        'fix', 'repair', 'service', 'maintenance', 'install', 'setup', 'configure',
        'password', 'login', 'access', 'account', 'printer', 'computer', 'laptop',
        'network', 'internet', 'email', 'phone', 'call', 'meeting', 'appointment',
        'invoice', 'quote', 'order', 'delivery', 'payment', 'refund',
        'complaint', 'feedback', 'suggestion', 'thank you', 'thanks',
        're:', 'fwd:', 'reply', 'response', 'follow up', 'following up',
        'tkt-', 'ticket #', 'case #', 'reference'
    ]
    
    # Spam indicators - if too many, skip this email
    spam_keywords = [
        'unsubscribe', 'click here', 'act now', 'limited time', 'free gift',
        'congratulations', 'you won', 'lottery', 'inheritance', 'million dollars',
        'viagra', 'cialis', 'pharmacy', 'weight loss', 'diet pill',
        'nigerian prince', 'wire transfer', 'western union', 'bitcoin',
        'cryptocurrency', 'investment opportunity', 'double your money',
        'no obligation', 'risk free', 'guaranteed', 'special offer',
        'dear friend', 'dear customer', 'dear sir/madam'
    ]
    
    # Known spam sender patterns
    spam_sender_patterns = [
        'noreply@', 'no-reply@', 'mailer-daemon', 'postmaster',
        'bounce', 'newsletter', 'marketing', 'promo', 'sales@',
        'info@', 'admin@', 'support@' # Generic addresses often used by spam
    ]
    
    # Count support indicators
    support_score = sum(1 for kw in support_keywords if kw in content)
    
    # Count spam indicators
    spam_score = sum(1 for kw in spam_keywords if kw in content)
    spam_score += sum(1 for pattern in spam_sender_patterns if pattern in sender)
    
    # Check for personal greeting (indicates real email)
    has_personal_greeting = any(greeting in content for greeting in [
        'hi ', 'hello ', 'dear ', 'good morning', 'good afternoon', 'good day'
    ])
    if has_personal_greeting:
        support_score += 2
    
    # If it looks like a reply to a ticket, it's definitely support
    if 'tkt-' in content or 'ticket #' in content:
        return True
    
    # Decision: needs more support indicators than spam indicators
    # and at least 2 support keywords to be considered a support query
    return support_score >= 2 and support_score > spam_score


async def generate_unique_ticket_number(db: AsyncSession, workspace_id: int) -> str:
    """Generate a unique ticket number by finding the max existing number GLOBALLY"""
    current_year = datetime.now().year
    prefix = f"TKT-{current_year}-"
    
    # Find the highest ticket number for this year GLOBALLY (across all workspaces)
    # because ticket_number is unique across the entire database
    result = await db.execute(
        select(Ticket.ticket_number)
        .where(Ticket.ticket_number.like(f"{prefix}%"))
    )
    existing_numbers = result.scalars().all()
    
    max_num = 0
    for tn in existing_numbers:
        try:
            # Extract the number part (e.g., "TKT-2025-00042" -> 42)
            num_part = int(tn.replace(prefix, ""))
            if num_part > max_num:
                max_num = num_part
        except (ValueError, AttributeError):
            continue
    
    # Generate next number
    next_num = max_num + 1
    return f"{prefix}{next_num:05d}"


class EmailToTicketService:
    """Service to process emails from IMAP and create tickets"""
    
    def __init__(self, email_settings: EmailSettings, workspace_id: int):
        self.settings = email_settings
        self.workspace_id = workspace_id
        
    def connect_imap(self):
        """Connect to IMAP server with timeout.
        
        Auto-detects Gmail/Google hosts and forces correct IMAP settings
        (port 993, SSL) regardless of what the user configured, since Gmail
        requires SSL on port 993 for IMAP access.
        """
        try:
            host = self.settings.incoming_mail_host or ''
            port = self.settings.incoming_mail_port
            use_ssl = self.settings.incoming_mail_use_ssl
            
            # Auto-detect Gmail/Google and force correct IMAP settings
            # Gmail REQUIRES SSL on port 993 — POP3 defaults (port 110, no SSL) will fail
            is_gmail = 'gmail' in host.lower() or 'google' in host.lower()
            if is_gmail:
                if not use_ssl or port in (None, 110, 143, 0):
                    print(f"[IMAP] Gmail detected ({host}) - forcing SSL on port 993 (was port={port}, ssl={use_ssl})")
                    _syslog('INFO', 'IMAP', f'Gmail detected - forcing SSL on port 993', f'Host={host} | OrigPort={port} | OrigSSL={use_ssl}')
                    use_ssl = True
                    port = 993
            
            if use_ssl:
                mail = imaplib.IMAP4_SSL(
                    host,
                    port or 993,
                    timeout=IMAP_TIMEOUT
                )
            else:
                mail = imaplib.IMAP4(
                    host,
                    port or 143
                )
            
            mail.login(
                self.settings.incoming_mail_username,
                self.settings.incoming_mail_password
            )
            print(f"[IMAP] Successfully connected to {host}:{port} (SSL={use_ssl})")
            _syslog('INFO', 'IMAP', f'Connected to {host}:{port}')
            return mail
        except Exception as e:
            print(f"[IMAP] Failed to connect to IMAP server {host}:{port} (SSL={use_ssl}): {e}")
            _syslog('ERROR', 'IMAP', f'Connection failed: {host}:{port}', str(e)[:200])
            raise
    
    def decode_header_value(self, header: str) -> str:
        """Decode email header"""
        if not header:
            return ""
        
        decoded_parts = decode_header(header)
        decoded_string = ""
        
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                decoded_string += part.decode(encoding or 'utf-8', errors='ignore')
            else:
                decoded_string += part
        
        return decoded_string
    
    def extract_email_address(self, from_header: str) -> Tuple[str, str]:
        """Extract name and email from 'From' header, with MIME decoding"""
        name, email_addr = parseaddr(from_header)
        # Decode MIME-encoded name (e.g. =?UTF-8?B?...?=)
        if name and ('=?' in name):
            name = self.decode_header_value(name)
        return name, email_addr.lower()
    
    def clean_email_body(self, body: str) -> str:
        """Clean email body - preserve full content including quoted/forwarded sections"""
        import re
        
        result = body.strip()
        
        # Clean up excessive whitespace 
        result = re.sub(r'\n{4,}', '\n\n\n', result)  # Max 3 consecutive newlines
        
        return result
    
    def determine_priority(self, subject: str, body: str) -> str:
        """Auto-detect priority from email subject only (not body, to avoid false matches).
        
        Only checks the subject line to avoid common words in email bodies
        like 'error', 'not working', 'down' triggering false urgent/high priority.
        """
        subject_lower = subject.lower()
        
        # Only match deliberate urgency markers in the subject line
        urgent_keywords = ['urgent', 'emergency', 'critical', 'asap']
        high_keywords = ['important', 'high priority']
        
        if any(keyword in subject_lower for keyword in urgent_keywords):
            return 'urgent'
        elif any(keyword in subject_lower for keyword in high_keywords):
            return 'high'
        else:
            return 'medium'
    
    def extract_email_body(self, msg) -> str:
        """Extract plain text body from email message, converting HTML if needed"""
        body = ""
        html_body = ""
        
        if msg.is_multipart():
            # Try to get both plain text and HTML versions
            for part in msg.walk():
                content_type = part.get_content_type()
                
                if content_type == "text/plain" and not body:
                    try:
                        payload = part.get_payload(decode=True)
                        charset = part.get_content_charset() or 'utf-8'
                        body = payload.decode(charset, errors='ignore')
                    except Exception as e:
                        _syslog('WARNING', 'IMAP', 'Failed to decode text/plain part', str(e)[:200])
                        continue
                
                elif content_type == "text/html" and not html_body:
                    try:
                        payload = part.get_payload(decode=True)
                        charset = part.get_content_charset() or 'utf-8'
                        html_body = payload.decode(charset, errors='ignore')
                    except Exception as e:
                        _syslog('WARNING', 'IMAP', 'Failed to decode text/html part', str(e)[:200])
                        continue
        else:
            content_type = msg.get_content_type()
            try:
                payload = msg.get_payload(decode=True)
                charset = msg.get_content_charset() or 'utf-8'
                decoded = payload.decode(charset, errors='ignore')
                
                if content_type == "text/html":
                    html_body = decoded
                else:
                    body = decoded
            except Exception as e:
                _syslog('WARNING', 'IMAP', 'Failed to decode email body, using raw payload', str(e)[:200])
                body = str(msg.get_payload())
        
        # If we only have HTML, convert it to plain text
        if not body and html_body:
            body = self.html_to_text(html_body)
        elif not body:
            body = "No content"
        
        return self.clean_email_body(body)
    
    def html_to_text(self, html: str) -> str:
        """Convert HTML email to clean plain text, preserving signature layout"""
        from html.parser import HTMLParser
        import re
        
        class HTMLToText(HTMLParser):
            def __init__(self):
                super().__init__()
                self.text = []
                self.skip = False
                self.current_href = None
                self.link_text = []
                self.in_link = False
                self.last_was_block = False
                
            def handle_starttag(self, tag, attrs):
                attrs_dict = dict(attrs)
                if tag in ['script', 'style', 'head']:
                    self.skip = True
                elif tag == 'br':
                    self.text.append('\n')
                    self.last_was_block = True
                elif tag == 'p':
                    if self.text and not self.last_was_block:
                        self.text.append('\n')
                    self.last_was_block = True
                elif tag == 'div':
                    if self.text and not self.last_was_block:
                        self.text.append('\n')
                    self.last_was_block = True
                elif tag in ['li']:
                    self.text.append('\n• ')
                    self.last_was_block = True
                elif tag == 'a':
                    self.current_href = attrs_dict.get('href', '')
                    self.in_link = True
                    self.link_text = []
                elif tag == 'hr':
                    self.text.append('\n' + '—' * 30 + '\n')
                    self.last_was_block = True
                elif tag == 'tr':
                    # New table row = new line
                    if self.text and not self.last_was_block:
                        self.text.append('\n')
                    self.last_was_block = True
                elif tag in ['td', 'th']:
                    # Table cells separated by a space (not pipes)
                    if self.text and self.text[-1] not in ['\n', '']:
                        last = self.text[-1].rstrip()
                        if last:
                            self.text.append('  ')
                elif tag == 'img':
                    # Show alt text for images (e.g. logo alt text)
                    alt = attrs_dict.get('alt', '').strip()
                    if alt:
                        self.text.append(alt)
                        self.last_was_block = False
                elif tag == 'blockquote':
                    self.text.append('\n')
                    self.last_was_block = True
                    
            def handle_endtag(self, tag):
                if tag in ['script', 'style', 'head']:
                    self.skip = False
                elif tag == 'a':
                    # Smart URL handling
                    href = self.current_href or ''
                    display = ''.join(self.link_text).strip()
                    
                    if href.startswith('mailto:'):
                        email_addr = href.replace('mailto:', '').split('?')[0]
                        # If link text is the same as the email, just show it once
                        if display and display != email_addr:
                            self.text.append(f'{display} ({email_addr})')
                        else:
                            self.text.append(email_addr)
                    elif href.startswith(('http://', 'https://')):
                        if display and display != href and not display.startswith('http'):
                            # Link text is meaningful (not just the URL)
                            self.text.append(f'{display} ({href})')
                        elif display:
                            # Link text IS the URL or similar - just show once
                            self.text.append(display)
                        else:
                            self.text.append(href)
                    elif display:
                        self.text.append(display)
                        
                    self.current_href = None
                    self.in_link = False
                    self.link_text = []
                    self.last_was_block = False
                elif tag in ['p', 'div', 'blockquote']:
                    if self.text and not self.last_was_block:
                        self.text.append('\n')
                    self.last_was_block = True
                elif tag == 'tr':
                    pass  # handled in starttag
                elif tag in ['table']:
                    if self.text and not self.last_was_block:
                        self.text.append('\n')
                    self.last_was_block = True
                elif tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                    self.text.append('\n')
                    self.last_was_block = True
                    
            def handle_data(self, data):
                if not self.skip:
                    cleaned = data.strip()
                    if cleaned:
                        if self.in_link:
                            self.link_text.append(cleaned)
                        else:
                            self.text.append(cleaned)
                        self.last_was_block = False
                    elif data and not self.last_was_block:
                        # Whitespace between inline elements
                        if self.text and self.text[-1] not in ['\n', '\n\n', '']:
                            self.text.append(' ')
        
        try:
            parser = HTMLToText()
            parser.feed(html)
            text = ''.join(parser.text)
            
            # Clean up extra whitespace but preserve signature formatting
            text = re.sub(r'\n{4,}', '\n\n', text)      # Max 2 consecutive newlines
            text = re.sub(r' {3,}', '  ', text)          # Max 2 consecutive spaces
            text = re.sub(r'\t+', ' ', text)              # Tabs to space
            text = re.sub(r'[ \t]+\n', '\n', text)        # Trailing whitespace on lines
            text = re.sub(r'\n[ \t]+\n', '\n\n', text)    # Lines with only whitespace
            text = text.strip()
            
            return text
        except Exception as e:
            print(f"Error converting HTML to text: {e}")
            _syslog('WARNING', 'IMAP', 'HTML to text conversion failed', str(e)[:200])
            # Fallback: strip all HTML tags
            return re.sub(r'<[^>]+>', '', html)
    
    async def is_email_processed(self, db: AsyncSession, message_id: str) -> bool:
        """Check if email was already processed by THIS account.
        Only checks the specific account — different accounts are allowed to
        independently process the same Message-ID (e.g. same email sent to
        multiple support addresses should create separate tickets)."""
        account_email = (self.settings.incoming_mail_username or '').lower()
        result = await db.execute(
            select(ProcessedMail).where(
                ProcessedMail.message_id == message_id,
                ProcessedMail.email_account == account_email
            )
        )
        return result.scalars().first() is not None
    
    async def find_ticket_by_reply(self, db: AsyncSession, in_reply_to: str, references: str):
        """Find ticket from reply headers (In-Reply-To or References).
        Returns: Ticket object, 'CLOSED' if reply belongs to a closed ticket, or None if no match."""
        print(f"[DEBUG] find_ticket_by_reply called with:")
        print(f"[DEBUG]   in_reply_to: '{in_reply_to}'")
        print(f"[DEBUG]   references: '{references}'")
        print(f"[DEBUG]   workspace_id: {self.workspace_id}")
        
        # Try In-Reply-To first
        if in_reply_to:
            print(f"[DEBUG] Searching processedmail for message_id: '{in_reply_to}'")
            result = await db.execute(
                select(ProcessedMail).where(
                    ProcessedMail.message_id == in_reply_to,
                    ProcessedMail.workspace_id == self.workspace_id
                )
            )
            processed = result.scalars().first()
            print(f"[DEBUG] ProcessedMail result: {processed}")
            if processed and processed.ticket_id:
                print(f"[DEBUG] Found ticket_id: {processed.ticket_id}")
                ticket_result = await db.execute(
                    select(Ticket).where(Ticket.id == processed.ticket_id)
                )
                ticket = ticket_result.scalar_one_or_none()
                if ticket and ticket.status in ['closed', 'resolved']:
                    print(f"[DEBUG] Found ticket #{ticket.ticket_number} but it's CLOSED - skipping email")
                    return 'CLOSED'
                print(f"[DEBUG] Returning ticket: {ticket.ticket_number if ticket else None}")
                return ticket
        
        # Try References (can contain multiple message IDs)
        found_closed = False
        if references:
            print(f"[DEBUG] Trying References header")
            # References format: "<msg1> <msg2> <msg3>"
            ref_ids = references.strip().split()
            print(f"[DEBUG] Parsed reference IDs: {ref_ids}")
            for ref_id in reversed(ref_ids):  # Check from newest to oldest
                # Keep angle brackets for matching
                ref_id = ref_id.strip()
                print(f"[DEBUG] Checking reference: '{ref_id}'")
                result = await db.execute(
                    select(ProcessedMail).where(
                        ProcessedMail.message_id == ref_id,
                        ProcessedMail.workspace_id == self.workspace_id
                    )
                )
                processed = result.scalars().first()
                if processed and processed.ticket_id:
                    ticket_result = await db.execute(
                        select(Ticket).where(Ticket.id == processed.ticket_id)
                    )
                    ticket = ticket_result.scalar_one_or_none()
                    if ticket and ticket.status in ['closed', 'resolved']:
                        print(f"[DEBUG] Found ticket #{ticket.ticket_number} via References but it's CLOSED")
                        found_closed = True
                        continue  # Try next reference
                    print(f"[DEBUG] Found ticket via References: {ticket.ticket_number if ticket else None}")
                    return ticket
        
        if found_closed:
            print(f"[DEBUG] All matched references point to closed tickets - skipping email")
            return 'CLOSED'
        
        print(f"[DEBUG] No ticket found via In-Reply-To or References")
        return None
    
    async def find_ticket_by_subject(self, db: AsyncSession, subject: str) -> Optional[Ticket]:
        """
        Fallback: Find ticket by subject line pattern
        Gmail/Outlook include "Re: Ticket #12345" or "Ticket #12345" in subject
        """
        import re
        
        print(f"[DEBUG] Trying to find ticket by subject: '{subject}'")
        
        # Clean up the subject - remove Re:, Fwd:, etc.
        clean_subject = re.sub(r'^(Re:|RE:|Fwd:|FWD:|\[.*?\])\s*', '', subject, flags=re.IGNORECASE).strip()
        print(f"[DEBUG] Cleaned subject: '{clean_subject}'")
        
        # Look for patterns like "Ticket #12345" or "#12345"
        patterns = [
            r'Ticket\s*#?\s*(\d+)',      # "Ticket #12345" or "Ticket 12345"
            r'Re:\s*Ticket\s*#?\s*(\d+)', # "Re: Ticket #12345"
            r'#(\d+)',                     # "#12345" anywhere
            r'\bticket\s*#?\s*(\d+)',      # "ticket 12345" (case insensitive)
            r'\[#(\d+)\]',                 # "[#12345]"
            r'(?:^|\s)(\d{5,})',           # 5+ digit number (likely ticket number)
        ]
        
        # Try on both original and cleaned subject
        for test_subject in [subject, clean_subject]:
            for pattern in patterns:
                match = re.search(pattern, test_subject, re.IGNORECASE)
                if match:
                    ticket_number = match.group(1)
                    print(f"[DEBUG] Found potential ticket number in subject: {ticket_number} (pattern: {pattern})")
                    
                    # Search for ticket by number
                    result = await db.execute(
                        select(Ticket).where(
                            Ticket.ticket_number == ticket_number,
                            Ticket.workspace_id == self.workspace_id
                        )
                    )
                    ticket = result.scalar_one_or_none()
                    if ticket:
                        # Don't add comments to closed tickets - create new ticket instead
                        if ticket.status in ['closed', 'resolved']:
                            print(f"[DEBUG] Found ticket #{ticket.ticket_number} but it's CLOSED - will create new ticket")
                            return None
                        print(f"[DEBUG] ✅ Found ticket #{ticket.ticket_number} via subject line")
                        return ticket
                    else:
                        print(f"[DEBUG] Pattern matched '{ticket_number}' but no ticket found in database")
        
        print(f"[DEBUG] ❌ No ticket number found in subject")
        return None
    
    async def find_ticket_by_sender(self, db: AsyncSession, sender_email: str) -> Optional[Ticket]:
        """
        Last resort fallback: Find most recent open ticket from this sender
        Only matches if there's exactly ONE open ticket from this email
        """
        print(f"[DEBUG] Trying to find ticket by sender email: '{sender_email}'")
        
        # Search for open tickets from this email (not closed)
        result = await db.execute(
            select(Ticket).where(
                Ticket.guest_email == sender_email,
                Ticket.workspace_id == self.workspace_id,
                Ticket.status.in_(['open', 'in_progress', 'waiting'])
            ).order_by(Ticket.created_at.desc())
        )
        tickets = result.scalars().all()
        
        if len(tickets) == 1:
            # Only auto-match if there's exactly one open ticket
            print(f"[DEBUG] ✅ Found single open ticket #{tickets[0].ticket_number} from sender")
            return tickets[0]
        elif len(tickets) > 1:
            print(f"[DEBUG] Found {len(tickets)} open tickets from sender - ambiguous, creating new ticket")
        else:
            print(f"[DEBUG] No open tickets found from sender")
        
        return None
    
    async def mark_email_processed(
        self, 
        db: AsyncSession, 
        message_id: str, 
        email_from: str, 
        subject: str, 
        ticket_id: Optional[int]
    ):
        """Mark email as processed - with duplicate protection"""
        try:
            account_email = (self.settings.incoming_mail_username or '').lower()
            processed = ProcessedMail(
                message_id=message_id,
                email_from=email_from,
                subject=subject,
                ticket_id=ticket_id,
                workspace_id=self.workspace_id,
                email_account=account_email,
                processed_at=get_local_time()
            )
            db.add(processed)
            await db.commit()
        except Exception as e:
            # Handle duplicate key error gracefully (already processed by another worker)
            if 'UNIQUE constraint' in str(e) or 'duplicate' in str(e).lower():
                print(f"[IMAP] Email already marked as processed (race condition handled): {message_id[:50]}")
                _syslog('WARNING', 'IMAP', 'Duplicate ProcessedMail entry (race condition)', f'MsgID={message_id[:80]}')
                await db.rollback()
            else:
                raise
    
    async def find_project_by_email(self, db: AsyncSession, to_email: str) -> Optional[Project]:
        """Find project by support email address"""
        if not to_email:
            return None
        
        to_email = to_email.lower().strip()
        print(f"[DEBUG] Looking for project with support_email: {to_email}")
        
        result = await db.execute(
            select(Project).where(
                Project.workspace_id == self.workspace_id,
                Project.support_email == to_email,
                Project.is_archived == False
            )
        )
        project = result.scalar_one_or_none()
        
        if project:
            print(f"[DEBUG] Found project: {project.name} (ID: {project.id})")
        else:
            print(f"[DEBUG] No project found for email: {to_email}")
        
        return project
    
    async def create_ticket_from_email(
        self,
        db: AsyncSession,
        sender_name: str,
        sender_email: str,
        subject: str,
        body: str,
        to_email: Optional[str] = None,
        project: Optional[Project] = None,
        attachments: Optional[List[dict]] = None
    ) -> Ticket:
        """Create a guest ticket from email"""
        
        # Generate unique ticket number
        ticket_number = await generate_unique_ticket_number(db, self.workspace_id)
        
        # Determine priority
        priority = self.determine_priority(subject, body)
        
        # Create ticket
        ticket = Ticket(
            ticket_number=ticket_number,
            subject=subject[:200],  # Limit subject length
            description=body[:5000],  # Limit body length
            priority=priority,
            status='open',
            category='support',
            workspace_id=self.workspace_id,
            created_by_id=None,  # Guest ticket
            is_guest=True,
            guest_name=sender_name.split()[0] if sender_name and sender_name.strip() else "Unknown",
            guest_surname=sender_name.split()[-1] if sender_name and len(sender_name.split()) > 1 else "",
            guest_email=sender_email,
            guest_phone="",
            guest_company="",
            guest_branch="",
            related_project_id=project.id if project else None,  # Link to project if found
            created_at=get_local_time(),
            updated_at=get_local_time()
        )
        
        db.add(ticket)
        await db.flush()
        
        # Add history entry
        history_comment = f'Ticket created automatically from email: {sender_email}'
        if project:
            history_comment += f' → Project: {project.name}'
        if to_email:
            history_comment += f' (to: {to_email})'
            
        history = TicketHistory(
            ticket_id=ticket.id,
            user_id=None,  # System action
            action='created',
            new_value=history_comment,
            created_at=get_local_time()
        )
        db.add(history)
        
        # Notify all admins about new email ticket
        from app.models.notification import Notification
        from app.models.user import User
        from sqlmodel import select as sql_select
        
        admin_users = (await db.execute(
            sql_select(User).where(User.workspace_id == self.workspace_id).where(User.is_admin == True)
        )).scalars().all()
        
        notification_message = f'New ticket from email #{ticket_number}: {subject[:100]}'
        if project:
            notification_message = f'New ticket for {project.name} from email #{ticket_number}: {subject[:100]}'
        
        for admin in admin_users:
            # Check if admin has muted ticket notifications
            if getattr(admin, 'mute_ticket_notifications', False):
                continue
            notification = Notification(
                user_id=admin.id,
                type='ticket',
                message=notification_message,
                url=f'/web/tickets/{ticket.id}',
                related_id=ticket.id
            )
            db.add(notification)
        
        # Save email attachments if any
        if attachments:
            try:
                await save_email_attachments(db, ticket.id, attachments)
            except Exception as e:
                print(f"[Email Attachment] Failed to save attachments for ticket {ticket.id}: {e}")
                _syslog('ERROR', 'IMAP', 'Attachment save failed', f'Ticket={ticket.id} | Error={str(e)[:200]}')
        
        await db.commit()
        await db.refresh(ticket)
        
        return ticket
    
    async def add_comment_from_email(
        self,
        db: AsyncSession,
        ticket: Ticket,
        sender_name: str,
        sender_email: str,
        body: str,
        attachments: Optional[List[dict]] = None
    ) -> TicketComment:
        """Add a comment to an existing ticket from email reply"""
        
        # Create comment
        comment = TicketComment(
            ticket_id=ticket.id,
            user_id=None,  # Guest comment from email
            content=f"**Email reply from {sender_name} ({sender_email}):**\n\n{body}",
            is_internal=False,
            created_at=get_local_time()
        )
        db.add(comment)
        
        # Update ticket timestamp
        ticket.updated_at = get_local_time()
        
        # Add history entry
        history = TicketHistory(
            ticket_id=ticket.id,
            user_id=None,
            action='comment_added',
            new_value=f'Email reply received from {sender_email}',
            created_at=get_local_time()
        )
        db.add(history)
        
        # Notify all non-admin users in the workspace about email reply
        from app.models.user import User
        from sqlmodel import select
        
        # Get all non-admin users in the workspace
        users_query = (
            select(User)
            .where(User.workspace_id == ticket.workspace_id)
            .where(User.is_admin == False)
        )
        non_admin_users = (await db.execute(users_query)).scalars().all()
        
        # Create notification for each non-admin user (if they haven't muted)
        for user in non_admin_users:
            # Check if user has muted ticket notifications
            if getattr(user, 'mute_ticket_notifications', False):
                continue
            notification = Notification(
                user_id=user.id,
                type='email_reply',
                message=f'📧 Email reply received on ticket #{ticket.ticket_number} from {sender_email}',
                url=f'/web/tickets/{ticket.id}',
                related_id=ticket.id
            )
            db.add(notification)
        
        # Save email attachments if any (linked to both ticket and comment)
        if attachments:
            try:
                await db.flush()  # Flush to get comment.id
                await save_email_attachments(db, ticket.id, attachments, comment_id=comment.id)
            except Exception as e:
                print(f"[Email Attachment] Failed to save attachments for ticket {ticket.id}: {e}")
                _syslog('ERROR', 'IMAP', 'Attachment save failed (comment)', f'Ticket={ticket.id} | Error={str(e)[:200]}')
        
        # Capture before commit — attributes expire on commit with direct AsyncSession
        ticket_num = ticket.ticket_number
        ws_id = ticket.workspace_id
        
        await db.commit()
        await db.refresh(comment)
        _syslog('INFO', 'IMAP', f'Comment added to ticket #{ticket_num}', f'From={sender_email} | CommentID={comment.id}', ws_id)
        
        return comment
    
    async def fetch_imap_emails(self, db: AsyncSession) -> List[Ticket]:
        """Fetch emails from IMAP server and create tickets.
        
        Uses asyncio.to_thread() to run blocking IMAP operations in a thread pool,
        preventing the event loop from blocking and keeping the website responsive.
        """
        tickets_created = []
        mail = None
        
        try:
            # Run blocking IMAP connection in a thread pool
            def connect_and_fetch():
                """Synchronous function to connect and fetch emails from all folders"""
                nonlocal mail
                mail = self.connect_imap()
                
                # Folders to check - INBOX gets all emails, others are filtered for support queries
                folders_to_check = [
                    ('INBOX', False),  # (folder_name, requires_analysis)
                    ('[Gmail]/Spam', True),
                    ('[Gmail]/Trash', True),
                    ('Spam', True),
                    ('Junk', True),
                    ('Trash', True),
                    ('INBOX.Spam', True),
                    ('INBOX.Junk', True),
                    ('INBOX.Trash', True),
                ]
                
                all_raw_emails = []
                
                for folder_name, requires_analysis in folders_to_check:
                    try:
                        status, _ = mail.select(folder_name)
                        if status != 'OK':
                            continue
                        
                        # Search for emails from the last 7 days
                        # Use UID commands for stable email identification across sessions
                        from datetime import datetime, timedelta
                        date_since = (datetime.now() - timedelta(days=7)).strftime("%d-%b-%Y")
                        status, messages = mail.uid('search', None, f'SINCE {date_since}')
                        email_ids = messages[0].split()
                        
                        if email_ids:
                            print(f"[IMAP] Found {len(email_ids)} messages in {folder_name}")
                        
                        for email_id in email_ids:
                            try:
                                status, msg_data = mail.uid('fetch', email_id, '(RFC822)')
                                if msg_data and msg_data[0]:
                                    all_raw_emails.append({
                                        'email_id': email_id,
                                        'msg_bytes': msg_data[0][1],
                                        'folder': folder_name,
                                        'requires_analysis': requires_analysis,
                                        'use_uid': True
                                    })
                            except Exception as e:
                                print(f"[IMAP] Error fetching email UID {email_id} from {folder_name}: {e}")
                                _syslog('WARNING', 'IMAP', f'Failed to fetch email UID {email_id} from {folder_name}', str(e)[:200])
                                continue
                    except Exception as e:
                        # Folder doesn't exist or can't be selected
                        _syslog('INFO', 'IMAP', f'Folder not available: {folder_name}', str(e)[:100])
                        continue
                
                # Don't re-select INBOX here - we'll select the correct folder when marking as read
                return all_raw_emails
            
            # Run IMAP fetch in thread pool (non-blocking)
            raw_emails = await asyncio.to_thread(connect_and_fetch)
            
            print(f"[IMAP] Found {len(raw_emails)} messages from last 7 days")
            _syslog('INFO', 'IMAP', f'Fetched {len(raw_emails)} emails from last 7 days')
            
            # Import for fresh sessions
            from sqlmodel.ext.asyncio.session import AsyncSession as NewAsyncSession
            from app.core.database import engine
            
            # Process each email with fresh db sessions to avoid greenlet issues
            for raw_email in raw_emails:
                email_id = raw_email['email_id']
                folder = raw_email.get('folder', 'INBOX')
                requires_analysis = raw_email.get('requires_analysis', False)
                try:
                    msg = email.message_from_bytes(raw_email['msg_bytes'])
                    
                    # Get message ID - use content hash as stable fallback if no Message-ID header
                    message_id = msg.get('Message-ID')
                    if not message_id:
                        import hashlib
                        raw_from = msg.get('From', '')
                        raw_subject = msg.get('Subject', '')
                        raw_date = msg.get('Date', '')
                        content_key = f"{raw_from}|{raw_subject}|{raw_date}"
                        content_hash = hashlib.sha256(content_key.encode()).hexdigest()[:32]
                        message_id = f'<no-id-{content_hash}@generated>'
                        print(f"[IMAP] No Message-ID header, generated stable ID from content hash: {message_id}")
                        _syslog('WARNING', 'IMAP', 'No Message-ID header, generated synthetic ID', f'ID={message_id}')
                    
                    # Helper to mark email as read in correct folder (using UID)
                    async def mark_as_read_in_folder(eid, fld):
                        """Select the correct folder and mark email as read using UID"""
                        def _mark():
                            mail.select(fld)
                            mail.uid('store', eid, '+FLAGS', '\\Seen')
                        await asyncio.to_thread(_mark)
                    
                    # Use fresh session for each email to avoid greenlet context issues
                    async with NewAsyncSession(engine) as fresh_db:
                        # Check if already processed
                        if await self.is_email_processed(fresh_db, message_id):
                            # Mark as read but don't process again (run in thread)
                            try:
                                await mark_as_read_in_folder(email_id, folder)
                            except Exception as e:
                                print(f"[IMAP] Warning: Could not mark email as read in {folder}: {e}")
                                _syslog('WARNING', 'IMAP', f'Failed to mark email as read in {folder}', str(e)[:200])
                            continue
                        
                        # Extract email info
                        from_header = msg.get('From', '')
                        sender_name, sender_email = self.extract_email_address(from_header)
                        to_header = msg.get('To', '')
                        _, to_email = self.extract_email_address(to_header)
                        
                        # Skip emails sent FROM our own address ONLY when TO is external
                        # FROM=self, TO=customer → outgoing reply, skip
                        # FROM=self, TO=self → form notification / system alert, process as new ticket
                        own_email = (self.settings.incoming_mail_username or '').lower()
                        smtp_from = (self.settings.smtp_from_email or '').lower() if hasattr(self.settings, 'smtp_from_email') else ''
                        own_addresses = {addr for addr in [own_email, smtp_from] if addr}
                        is_from_self = sender_email and sender_email.lower() in own_addresses
                        is_to_self = to_email and to_email.lower() in own_addresses
                        if is_from_self and not is_to_self:
                            print(f"[IMAP] ⏭️ SKIPPING: Outgoing reply from our address ({sender_email}) to external ({to_email})")
                            _syslog('INFO', 'IMAP', 'Skipped own outgoing email', f'From={sender_email}')
                            await self.mark_email_processed(fresh_db, message_id, sender_email,
                                self.decode_header_value(msg.get('Subject', 'No Subject')), None)
                            try:
                                await mark_as_read_in_folder(email_id, folder)
                            except Exception as e:
                                print(f"[IMAP] Warning: Could not mark email as read in {folder}: {e}")
                                _syslog('WARNING', 'IMAP', f'Failed to mark email as read in {folder}', str(e)[:200])
                            continue
                        
                        subject = self.decode_header_value(msg.get('Subject', 'No Subject'))
                        body = self.extract_email_body(msg)
                        
                        # Extract attachments from the email
                        email_attachments = extract_email_attachments(msg)
                        
                        print(f"\n{'='*80}")
                        print(f"[IMAP] Processing email from folder: {folder}")
                        print(f"[IMAP] From: {sender_name} <{sender_email}>")
                        print(f"[IMAP] To: {to_email}")
                        print(f"[IMAP] Subject: {subject}")
                        print(f"[IMAP] Message-ID: {message_id}")
                        _syslog('INFO', 'IMAP', f'Processing: {subject[:80]}', f'From={sender_email} | MsgID={message_id[:80]} | Folder={folder}')
                        
                        # Check if this is a reply to an existing ticket
                        # Keep Message-ID with angle brackets for matching
                        in_reply_to = msg.get('In-Reply-To', '').strip()
                        references = msg.get('References', '').strip()
                        
                        print(f"[IMAP] In-Reply-To: '{in_reply_to}'")
                        print(f"[IMAP] References: '{references}'")
                        
                        existing_ticket = await self.find_ticket_by_reply(fresh_db, in_reply_to, references)
                        
                        # If reply belongs to a closed/resolved ticket, skip this email entirely
                        if existing_ticket == 'CLOSED':
                            print(f"[IMAP] ⏭️ SKIPPING: Email is a reply to a closed/resolved ticket")
                            _syslog('INFO', 'IMAP', 'Skipped reply to closed ticket', f'Subject={subject[:80]} | From={sender_email}')
                            await self.mark_email_processed(fresh_db, message_id, sender_email, subject, None)
                            try:
                                await mark_as_read_in_folder(email_id, folder)
                            except Exception as e:
                                print(f"[IMAP] Warning: Could not mark email as read in {folder}: {e}")
                                _syslog('WARNING', 'IMAP', f'Failed to mark email as read in {folder}', str(e)[:200])
                            continue
                        
                        # If not found via headers, try by sender email
                        # (Skip subject matching - too aggressive, catches invoice numbers etc.)
                        # NEVER use sender fallback for our own address — the support mailbox
                        # has many open tickets, so it would match everything to one ticket
                        if not existing_ticket and not is_from_self:
                            print(f"[IMAP] Trying sender email fallback...")
                            existing_ticket = await self.find_ticket_by_sender(fresh_db, sender_email)
                        elif not existing_ticket and is_from_self:
                            print(f"[IMAP] Skipping sender fallback (email is from our own address)")
                        
                        if existing_ticket:
                            print(f"[IMAP] ✅ MATCH FOUND - Adding to ticket #{existing_ticket.ticket_number}")
                            _syslog('INFO', 'IMAP', f'Matched to ticket #{existing_ticket.ticket_number}', f'From={sender_email} | Subject={subject[:80]}')
                        else:
                            print(f"[IMAP] ❌ NO MATCH - Will create new ticket")
                            _syslog('INFO', 'IMAP', 'No match - will create new ticket', f'From={sender_email} | Subject={subject[:80]} | InReplyTo={in_reply_to[:60]} | Refs={references[:60]}')
                        print(f"{'='*80}\n")
                        
                        # Find project by support email
                        project = await self.find_project_by_email(fresh_db, to_email)
                        
                        if existing_ticket:
                            # Refresh to ensure all attributes are loaded
                            await fresh_db.refresh(existing_ticket)
                            existing_ticket_id = existing_ticket.id
                            existing_ticket_number = existing_ticket.ticket_number
                            
                            # Add as comment to existing ticket
                            await self.add_comment_from_email(
                                fresh_db, existing_ticket, sender_name, sender_email, body,
                                attachments=email_attachments
                            )
                            
                            # Mark as processed
                            await self.mark_email_processed(
                                fresh_db, message_id, sender_email, subject, existing_ticket_id
                            )
                            
                            # Mark email as read in correct folder (run in thread)
                            try:
                                await mark_as_read_in_folder(email_id, folder)
                            except Exception as e:
                                print(f"[IMAP] Warning: Could not mark email as read in {folder}: {e}")
                                _syslog('WARNING', 'IMAP', f'Failed to mark email as read in {folder}', str(e)[:200])
                            
                            print(f"[IMAP] Added comment to ticket {existing_ticket_number} from {sender_email}")
                        else:
                            # Safety check: prevent duplicate ticket creation if this Message-ID
                            # was already processed by THIS account and has a ticket.
                            # This catches cases where ProcessedMail records were lost/invalidated.
                            # Per-account only — different accounts create their own tickets.
                            account_email_imap = (self.settings.incoming_mail_username or '').lower()
                            existing_pm = await fresh_db.execute(
                                select(ProcessedMail).where(
                                    ProcessedMail.message_id == message_id,
                                    ProcessedMail.email_account == account_email_imap,
                                    ProcessedMail.ticket_id.isnot(None)
                                )
                            )
                            already_has_ticket = existing_pm.scalars().first()
                            if already_has_ticket:
                                print(f"[IMAP] ⏭️ SKIPPING: Message-ID already has ticket #{already_has_ticket.ticket_id} in this workspace (safety dedup)")
                                _syslog('INFO', 'IMAP', 'Skipped duplicate Message-ID (safety)', f'From={sender_email} | Subject={subject[:80]} | ExistingTicket={already_has_ticket.ticket_id}')
                                await self.mark_email_processed(fresh_db, message_id, sender_email, subject, already_has_ticket.ticket_id)
                                try:
                                    await mark_as_read_in_folder(email_id, folder)
                                except Exception:
                                    pass
                                continue

                            # For spam/junk folders, check if this is a support query first
                            if requires_analysis:
                                if not is_support_query(subject, body, sender_email):
                                    print(f"[IMAP] ⏭️ SKIPPING: Email from {folder} folder doesn't look like a support query")
                                    print(f"[IMAP]    Subject: {subject[:50]}...")
                                    _syslog('INFO', 'IMAP', f'Non-support email skipped from {folder}', f'From={sender_email} | Subject={subject[:80]}')
                                    # Mark as read but don't create ticket
                                    try:
                                        await mark_as_read_in_folder(email_id, folder)
                                    except Exception as e:
                                        print(f"[IMAP] Warning: Could not mark email as read in {folder}: {e}")
                                    # Mark as processed to avoid checking again
                                    await self.mark_email_processed(
                                        fresh_db, message_id, sender_email, subject, None
                                    )
                                    continue
                                else:
                                    print(f"[IMAP] ✅ Email from {folder} folder looks like a support query - creating ticket")
                                    _syslog('INFO', 'IMAP', f'Support query found in {folder} - creating ticket', f'From={sender_email} | Subject={subject[:80]}')
                            
                            # Always create tickets (linked to project if matched)
                            ticket = await self.create_ticket_from_email(
                                fresh_db, sender_name, sender_email, subject, body, to_email, project,
                                attachments=email_attachments
                            )
                            
                            # Refresh and store ID immediately
                            await fresh_db.refresh(ticket)
                            ticket_id = ticket.id
                            ticket_number = ticket.ticket_number
                            
                            # Mark as processed
                            await self.mark_email_processed(
                                fresh_db, message_id, sender_email, subject, ticket_id
                            )
                            
                            # Mark email as read in correct folder (run in thread)
                            try:
                                await mark_as_read_in_folder(email_id, folder)
                            except Exception as e:
                                print(f"[IMAP] Warning: Could not mark email as read in {folder}: {e}")
                                _syslog('WARNING', 'IMAP', f'Failed to mark email as read in {folder}', str(e)[:200])
                            
                            tickets_created.append(ticket)
                            if project:
                                print(f"[IMAP] Created ticket {ticket_number} for project '{project.name}' from {sender_email} (folder: {folder})")
                            else:
                                print(f"[IMAP] Created ticket {ticket_number} from {sender_email} (folder: {folder})")
                            _syslog('INFO', 'IMAP', f'Created ticket #{ticket_number}', f'From={sender_email} | Subject={subject[:80]} | Folder={folder} | MsgID={message_id[:80]}')
                    
                except Exception as e:
                    err_str = str(e).lower()
                    if 'database is locked' in err_str or 'locked' in err_str:
                        print(f"[IMAP] ⚠️ Database locked while processing email {email_id} - will retry next cycle")
                        _syslog('WARNING', 'IMAP', f'Database locked', f'UID={email_id} | Will retry next cycle')
                        break  # Stop processing — DB unavailable
                    print(f"[IMAP] Error processing email {email_id}: {e}")
                    _syslog('ERROR', 'IMAP', f'Error processing email', f'UID={email_id} | Error={str(e)[:200]}')
                    continue
            
            # Close connection in thread pool
            if mail:
                await asyncio.to_thread(lambda: (mail.close(), mail.logout()))
                _syslog('INFO', 'IMAP', 'IMAP connection closed successfully')
            
        except Exception as e:
            print(f"[IMAP] Error fetching emails: {e}")
            _syslog('ERROR', 'IMAP', 'Error fetching emails', str(e)[:200])
            if mail:
                try:
                    await asyncio.to_thread(lambda: (mail.close(), mail.logout()))
                except Exception as close_e:
                    _syslog('WARNING', 'IMAP', 'IMAP close/logout failed on error path', str(close_e)[:200])
        
        return tickets_created
    
    async def process_emails(self, db: AsyncSession) -> List[Ticket]:
        """Process emails from IMAP server"""
        return await self.fetch_imap_emails(db)


async def process_workspace_emails(db: AsyncSession, workspace_id: int) -> List[Ticket]:
    """
    Process emails for a workspace using its email settings
    
    Args:
        db: Database session
        workspace_id: Workspace ID
        
    Returns:
        List of created tickets
    """
    # Get email settings
    result = await db.execute(
        select(EmailSettings).where(EmailSettings.workspace_id == workspace_id)
    )
    settings = result.scalar_one_or_none()
    
    if not settings:
        print(f"[Email] No email settings found for workspace {workspace_id}")
        return []
    
    if not settings.incoming_mail_host:
        print(f"[Email] Incoming mail not configured for workspace {workspace_id}")
        return []
    
    # Log the settings being used for debugging
    print(f"[Email] Workspace {workspace_id}: host={settings.incoming_mail_host}, "
          f"port={settings.incoming_mail_port}, type={settings.incoming_mail_type}, "
          f"ssl={settings.incoming_mail_use_ssl}, user={settings.incoming_mail_username}")
    
    # Create service and process emails (always uses IMAP — connect_imap auto-detects Gmail)
    service = EmailToTicketService(settings, workspace_id)
    return await service.process_emails(db)


async def find_ticket_by_reply_for_account(
    db: AsyncSession, 
    workspace_id: int, 
    in_reply_to: str, 
    references: str
):
    """Find ticket from reply headers (In-Reply-To or References) for alternate email accounts.
    Returns: Ticket object, 'CLOSED' if reply belongs to a closed ticket, or None if no match."""
    print(f"[DEBUG] find_ticket_by_reply_for_account called with:")
    print(f"[DEBUG]   in_reply_to: '{in_reply_to}'")
    print(f"[DEBUG]   references: '{references}'")
    print(f"[DEBUG]   workspace_id: {workspace_id}")
    
    # Try In-Reply-To first
    if in_reply_to:
        print(f"[DEBUG] Searching processedmail for message_id: '{in_reply_to}'")
        result = await db.execute(
            select(ProcessedMail).where(
                ProcessedMail.message_id == in_reply_to,
                ProcessedMail.workspace_id == workspace_id
            )
        )
        processed = result.scalars().first()
        print(f"[DEBUG] ProcessedMail result: {processed}")
        if processed and processed.ticket_id:
            print(f"[DEBUG] Found ticket_id: {processed.ticket_id}")
            ticket_result = await db.execute(
                select(Ticket).where(Ticket.id == processed.ticket_id)
            )
            ticket = ticket_result.scalar_one_or_none()
            if ticket and ticket.status in ['closed', 'resolved']:
                print(f"[DEBUG] Found ticket #{ticket.ticket_number} but it's CLOSED - skipping email")
                return 'CLOSED'
            print(f"[DEBUG] Returning ticket: {ticket.ticket_number if ticket else None}")
            return ticket
    
    # Try References (can contain multiple message IDs)
    found_closed = False
    if references:
        print(f"[DEBUG] Trying References header")
        ref_ids = references.strip().split()
        print(f"[DEBUG] Parsed reference IDs: {ref_ids}")
        for ref_id in reversed(ref_ids):  # Check from newest to oldest
            ref_id = ref_id.strip()
            print(f"[DEBUG] Checking reference: '{ref_id}'")
            result = await db.execute(
                select(ProcessedMail).where(
                    ProcessedMail.message_id == ref_id,
                    ProcessedMail.workspace_id == workspace_id
                )
            )
            processed = result.scalars().first()
            if processed and processed.ticket_id:
                ticket_result = await db.execute(
                    select(Ticket).where(Ticket.id == processed.ticket_id)
                )
                ticket = ticket_result.scalar_one_or_none()
                if ticket and ticket.status in ['closed', 'resolved']:
                    print(f"[DEBUG] Found ticket #{ticket.ticket_number} via References but it's CLOSED")
                    found_closed = True
                    continue  # Try next reference
                print(f"[DEBUG] Found ticket via References: {ticket.ticket_number if ticket else None}")
                return ticket
    
    if found_closed:
        print(f"[DEBUG] All matched references point to closed tickets - skipping email")
        return 'CLOSED'
    
    print(f"[DEBUG] No ticket found via In-Reply-To or References")
    return None


async def find_ticket_by_sender_for_account(db: AsyncSession, workspace_id: int, sender_email: str) -> Optional[Ticket]:
    """
    Last resort fallback: Find most recent open ticket from this sender
    Only matches if there's exactly ONE open ticket from this email
    """
    print(f"[DEBUG] Trying to find ticket by sender email: '{sender_email}'")
    
    # Search for open tickets from this email (not closed)
    result = await db.execute(
        select(Ticket).where(
            Ticket.guest_email == sender_email,
            Ticket.workspace_id == workspace_id,
            Ticket.status.in_(['open', 'in_progress', 'waiting'])
        ).order_by(Ticket.created_at.desc())
    )
    tickets = result.scalars().all()
    
    if len(tickets) == 1:
        # Only auto-match if there's exactly one open ticket
        print(f"[DEBUG] ✅ Found single open ticket #{tickets[0].ticket_number} from sender")
        return tickets[0]
    elif len(tickets) > 1:
        print(f"[DEBUG] Found {len(tickets)} open tickets from sender - ambiguous, creating new ticket")
    else:
        print(f"[DEBUG] No open tickets found from sender")
    
    return None


async def add_comment_from_email_for_account(
    db: AsyncSession,
    ticket: Ticket,
    sender_name: str,
    sender_email: str,
    body: str,
    attachments: Optional[List[dict]] = None
) -> TicketComment:
    """Add a comment to an existing ticket from email reply (for alternate email accounts)"""
    
    # Create comment
    comment = TicketComment(
        ticket_id=ticket.id,
        user_id=None,  # Guest comment from email
        content=f"**Email reply from {sender_name} ({sender_email}):**\n\n{body}",
        is_internal=False,
        created_at=get_local_time()
    )
    db.add(comment)
    
    # Update ticket timestamp
    ticket.updated_at = get_local_time()
    
    # Add history entry
    history = TicketHistory(
        ticket_id=ticket.id,
        user_id=None,
        action='comment_added',
        new_value=f'Email reply received from {sender_email}',
        created_at=get_local_time()
    )
    db.add(history)
    
    # Notify all non-admin users in the workspace about email reply
    from app.models.user import User
    
    # Get all non-admin users in the workspace
    users_query = (
        select(User)
        .where(User.workspace_id == ticket.workspace_id)
        .where(User.is_admin == False)
    )
    non_admin_users = (await db.execute(users_query)).scalars().all()
    
    # Create notification for each non-admin user (if they haven't muted)
    for user in non_admin_users:
        # Check if user has muted ticket notifications
        if getattr(user, 'mute_ticket_notifications', False):
            continue
        notification = Notification(
            user_id=user.id,
            type='email_reply',
            message=f'📧 Email reply received on ticket #{ticket.ticket_number} from {sender_email}',
            url=f'/web/tickets/{ticket.id}',
            related_id=ticket.id
        )
        db.add(notification)
    
    # Save email attachments if any (linked to both ticket and comment)
    if attachments:
        try:
            await db.flush()  # Flush to get comment.id
            await save_email_attachments(db, ticket.id, attachments, comment_id=comment.id)
        except Exception as e:
            print(f"[Email Attachment] Failed to save attachments for ticket {ticket.id}: {e}")
            _syslog('ERROR', 'Email Account', 'Attachment save failed (comment)', f'Ticket={ticket.id} | Error={str(e)[:200]}')
    
    # Capture before commit — attributes expire on commit with direct AsyncSession
    ticket_num = ticket.ticket_number
    ws_id = ticket.workspace_id
    
    await db.commit()
    await db.refresh(comment)
    _syslog('INFO', 'Email Account', f'Comment added to ticket #{ticket_num}', f'From={sender_email} | CommentID={comment.id}', ws_id)
    
    return comment


def _html_to_text_standalone(html: str) -> str:
    """Standalone HTML-to-text converter for use outside the EmailToTicketService class"""
    return EmailToTicketService.html_to_text(None, html)


def _clean_email_body_standalone(body: str) -> str:
    """Standalone email body cleaner for use outside the EmailToTicketService class"""
    return EmailToTicketService.clean_email_body(None, body)


async def process_email_account(db: AsyncSession, account) -> List[Ticket]:
    """
    Process emails for an IncomingEmailAccount and create tickets or add comments to existing tickets.
    
    Uses asyncio.to_thread() for blocking IMAP operations to prevent
    blocking the event loop and slowing down the website.
    
    Now supports reply detection via:
    1. In-Reply-To / References headers
    2. Subject line pattern matching (e.g., "Re: Ticket #TKT-2025-00042")
    3. Sender email fallback (single open ticket from same sender)
    
    Args:
        db: Database session
        account: IncomingEmailAccount with IMAP settings
        
    Returns:
        List of created tickets (replies to existing tickets are not included)
    """
    from app.core.database import engine
    from sqlmodel.ext.asyncio.session import AsyncSession as NewAsyncSession
    from app.models.processed_mail import ProcessedMail
    from app.models.notification import Notification
    from app.models.user import User
    
    if not account.imap_host or not account.imap_username:
        return []
    
    # Store account data we need before any async operations
    account_name = account.name
    account_email = account.email_address
    workspace_id = account.workspace_id
    project_id = account.project_id  # Link tickets to this project
    imap_host = account.imap_host
    imap_port = account.imap_port
    imap_username = account.imap_username
    imap_password = account.imap_password
    imap_use_ssl = account.imap_use_ssl
    protocol = getattr(account, 'protocol', 'imap')  # Default to IMAP for backward compatibility
    default_priority = account.default_priority
    default_category = account.default_category
    auto_assign_to_user_id = account.auto_assign_to_user_id
    
    tickets_created = []
    mail = None
    pop3_conn = None
    
    try:
        import imaplib
        import poplib
        import email as email_lib
        from email.header import decode_header
        from email.utils import parseaddr
        
        # Run blocking mail operations in thread pool
        def connect_and_fetch():
            """Synchronous mail connection and fetch (IMAP or POP3)"""
            nonlocal mail, pop3_conn
            
            # Auto-detect Gmail and force correct settings
            is_gmail = 'gmail' in imap_host.lower() or 'google' in imap_host.lower()
            effective_ssl = imap_use_ssl
            effective_port = imap_port
            
            if is_gmail and protocol != 'pop3':
                # Gmail REQUIRES SSL on port 993 for IMAP
                if not effective_ssl or effective_port in (None, 110, 143, 0):
                    print(f"[Email Account] Gmail detected ({imap_host}) - forcing SSL on port 993 (was port={effective_port}, ssl={effective_ssl})")
                    effective_ssl = True
                    effective_port = 993
            
            if protocol == 'pop3':
                # POP3 connection with timeout
                print(f"[Email Account] Using POP3 protocol on {imap_host}:{imap_port}")
                if imap_use_ssl:
                    pop3_conn = poplib.POP3_SSL(imap_host, imap_port or 995, timeout=IMAP_TIMEOUT)
                else:
                    pop3_conn = poplib.POP3(imap_host, imap_port or 110, timeout=IMAP_TIMEOUT)
                
                pop3_conn.user(imap_username)
                pop3_conn.pass_(imap_password)
                
                # Get message count
                num_messages = len(pop3_conn.list()[1])
                print(f"[Email Account] POP3: Found {num_messages} messages")
                _syslog('INFO', 'Email Account', f'POP3 connected to {imap_host}:{imap_port}', f'Messages={num_messages}', workspace_id)
                
                raw_emails = []
                # Only get last 50 messages to avoid overwhelming
                start_idx = max(1, num_messages - 50 + 1)
                for i in range(start_idx, num_messages + 1):
                    try:
                        response = pop3_conn.retr(i)
                        msg_bytes = b'\r\n'.join(response[1])
                        raw_emails.append({
                            'email_id': str(i).encode(),
                            'msg_bytes': msg_bytes
                        })
                    except Exception as e:
                        print(f"[Email Account] POP3 error fetching message {i}: {e}")
                        _syslog('WARNING', 'Email Account', f'POP3 fetch error for message {i}', str(e)[:200], workspace_id)
                        continue
                
                return raw_emails
            else:
                # IMAP connection (default) with timeout
                print(f"[Email Account] Using IMAP protocol on {imap_host}:{effective_port} (SSL={effective_ssl})")
                if effective_ssl:
                    mail = imaplib.IMAP4_SSL(imap_host, effective_port or 993, timeout=IMAP_TIMEOUT)
                else:
                    # Non-SSL connection - try STARTTLS for security
                    mail = imaplib.IMAP4(imap_host, effective_port or 143)
                    try:
                        mail.starttls()
                    except Exception as e:
                        # Server doesn't support STARTTLS, continue without encryption
                        _syslog('WARNING', 'Email Account', f'STARTTLS failed for {imap_host}', str(e)[:200], workspace_id)
                
                mail.login(imap_username, imap_password)
                _syslog('INFO', 'Email Account', f'IMAP connected to {imap_host}:{effective_port}', f'SSL={effective_ssl}', workspace_id)
                
                # Check multiple folders - INBOX plus Gmail-specific folders
                # Gmail may route emails to spam/promotions/etc.
                folders_to_check = ['INBOX']
                
                # Add Gmail-specific folders if it looks like a Gmail server
                if 'gmail' in imap_host.lower() or 'google' in imap_host.lower():
                    folders_to_check.extend([
                        '[Gmail]/Spam',
                    ])
                    # NOTE: Do NOT add [Gmail]/All Mail — it contains duplicates of
                    # every INBOX email, causing double-processing and folder state bugs
                
                # Fetch emails from the last 7 days (not just unread)
                # This ensures we catch emails even if marked as read by phone/webmail
                from datetime import datetime, timedelta
                date_since = (datetime.now() - timedelta(days=7)).strftime("%d-%b-%Y")
                
                raw_emails = []
                for folder in folders_to_check:
                    try:
                        status, _ = mail.select(folder)
                        if status != 'OK':
                            continue
                        
                        # Use UID commands for stable email identification across sessions
                        status, messages = mail.uid('search', None, f'SINCE {date_since}')
                        email_ids = messages[0].split()
                        
                        if email_ids:
                            print(f"[Email Account] Found {len(email_ids)} messages from last 7 days in {folder}")
                        
                        for email_id in email_ids:
                            try:
                                status, msg_data = mail.uid('fetch', email_id, '(RFC822)')
                                if msg_data and msg_data[0]:
                                    raw_emails.append({
                                        'email_id': email_id,
                                        'msg_bytes': msg_data[0][1],
                                        'folder': folder  # Track which folder this came from
                                    })
                            except Exception as e:
                                print(f"[Email Account] Error fetching email {email_id} from {folder}: {e}")
                                _syslog('WARNING', 'Email Account', f'Failed to fetch email {email_id} from {folder}', str(e)[:200], workspace_id)
                                continue
                    except Exception as e:
                        # Folder doesn't exist or can't be selected
                        _syslog('INFO', 'Email Account', f'Folder not available: {folder}', str(e)[:100], workspace_id)
                        continue
                
                return raw_emails
        
        # Fetch emails in thread pool (non-blocking)
        raw_emails = await asyncio.to_thread(connect_and_fetch)
        
        print(f"[Email Account] {account_name}: Found {len(raw_emails)} unread messages to process")
        _syslog('INFO', 'Email Account', f'{account_name}: Fetched {len(raw_emails)} emails', workspace_id=workspace_id)
        
        for raw_email in raw_emails:
            email_id = raw_email['email_id']
            email_folder = raw_email.get('folder', 'INBOX')  # Track folder for marking as read
            try:
                msg = email_lib.message_from_bytes(raw_email['msg_bytes'])
                
                # Get message ID - use content hash as stable fallback if no Message-ID header
                message_id = msg.get('Message-ID')
                if not message_id:
                    import hashlib
                    raw_from = msg.get('From', '')
                    raw_subject = msg.get('Subject', '')
                    raw_date = msg.get('Date', '')
                    content_key = f"{raw_from}|{raw_subject}|{raw_date}"
                    content_hash = hashlib.sha256(content_key.encode()).hexdigest()[:32]
                    message_id = f'<no-id-{content_hash}@generated>'
                    print(f"[Email Account] No Message-ID header, generated stable ID from content hash: {message_id}")
                    _syslog('WARNING', 'Email Account', 'No Message-ID header, generated synthetic ID', f'ID={message_id}', workspace_id)
                
                print(f"[Email Account] Processing email {email_id}: Message-ID={message_id[:50]}...")
                
                # Use a fresh database session for each email to avoid greenlet issues
                async with NewAsyncSession(engine) as fresh_db:
                    # Check if already processed by THIS account only.
                    # Different accounts process independently — same email sent to
                    # multiple support addresses should create separate tickets.
                    existing = await fresh_db.execute(
                        select(ProcessedMail).where(
                            ProcessedMail.message_id == message_id,
                            ProcessedMail.email_account == account_email.lower()
                        )
                    )
                    already_processed = existing.scalars().first() is not None
                    if already_processed:
                        print(f"[Email Account] Email already processed, marking as read")
                        if mail:
                            try:
                                # Capture variables by value using default arguments to avoid closure bug
                                def _mark_read_1(_folder=email_folder, _eid=email_id):
                                    mail.select(_folder)
                                    mail.uid('store', _eid, '+FLAGS', '\\Seen')
                                await asyncio.to_thread(_mark_read_1)
                            except Exception as e:
                                print(f"[Email Account] Warning: Could not mark email as read: {e}")
                                _syslog('WARNING', 'Email Account', 'Failed to mark email as read', str(e)[:200], workspace_id)
                        continue
                    
                    # Extract email info
                    from_header = msg.get('From', '')
                    sender_name, sender_email_addr = parseaddr(from_header)
                    sender_email_addr = sender_email_addr.lower() if sender_email_addr else ''
                    # Decode MIME-encoded name (e.g. =?UTF-8?B?...?=)
                    if sender_name and ('=?' in sender_name):
                        decoded_parts = decode_header(sender_name)
                        sender_name = ''
                        for part, charset in decoded_parts:
                            if isinstance(part, bytes):
                                sender_name += part.decode(charset or 'utf-8', errors='replace')
                            else:
                                sender_name += part
                    
                    # Decode subject
                    subject_header = msg.get('Subject', 'No Subject')
                    if isinstance(subject_header, bytes):
                        subject = subject_header.decode()
                    else:
                        decoded = decode_header(subject_header)
                        subject = ''
                        for part, charset in decoded:
                            if isinstance(part, bytes):
                                subject += part.decode(charset or 'utf-8', errors='replace')
                            else:
                                subject += part
                    
                    # Extract To header for outgoing email detection
                    to_header = msg.get('To', '')
                    _, to_email_addr = parseaddr(to_header)
                    to_email_addr = to_email_addr.lower() if to_email_addr else ''
                    
                    print(f"[Email Account] From: {sender_name} <{sender_email_addr}>")
                    print(f"[Email Account] To: {to_email_addr}")
                    print(f"[Email Account] Subject: {subject}")
                    _syslog('INFO', 'Email Account', f'Processing: {subject[:80]}', f'From={sender_email_addr} | MsgID={message_id[:80]}', workspace_id)
                    
                    # Skip emails sent FROM our own address (outgoing replies)
                    # But ONLY if the email is NOT addressed TO our own address
                    # (self-addressed emails like form notifications, toner requests etc. should still be processed)
                    own_addresses = {imap_username.lower(), account_email.lower()}
                    is_from_self = sender_email_addr and sender_email_addr in own_addresses
                    is_to_self = to_email_addr and to_email_addr in own_addresses
                    if is_from_self and not is_to_self:
                        print(f"[Email Account] ⏭️ SKIPPING: Email sent from our own address ({sender_email_addr}) to external recipient ({to_email_addr})")
                        _syslog('INFO', 'Email Account', 'Skipped own outgoing email', f'From={sender_email_addr}', workspace_id)
                        processed = ProcessedMail(
                            message_id=message_id,
                            email_from=sender_email_addr,
                            subject=subject,
                            ticket_id=None,
                            workspace_id=workspace_id,
                            email_account=account_email.lower(),
                            processed_at=get_local_time()
                        )
                        fresh_db.add(processed)
                        await fresh_db.commit()
                        if mail:
                            try:
                                def _mark_read_self(_folder=email_folder, _eid=email_id):
                                    mail.select(_folder)
                                    mail.uid('store', _eid, '+FLAGS', '\\Seen')
                                await asyncio.to_thread(_mark_read_self)
                            except Exception as e:
                                print(f"[Email Account] Warning: Could not mark email as read: {e}")
                                _syslog('WARNING', 'Email Account', 'Failed to mark email as read', str(e)[:200], workspace_id)
                        continue
                    
                    # Get reply headers for threading detection
                    in_reply_to = msg.get('In-Reply-To', '').strip()
                    references = msg.get('References', '').strip()
                    
                    print(f"[Email Account] In-Reply-To: '{in_reply_to}'")
                    print(f"[Email Account] References: '{references}'")
                    
                    # Extract body (try plain text first, fall back to HTML)
                    body = ''
                    html_body = ''
                    if msg.is_multipart():
                        for part in msg.walk():
                            content_type = part.get_content_type()
                            if content_type == 'text/plain' and not body:
                                payload = part.get_payload(decode=True)
                                if payload:
                                    charset = part.get_content_charset() or 'utf-8'
                                    body = payload.decode(charset, errors='replace')
                            elif content_type == 'text/html' and not html_body:
                                payload = part.get_payload(decode=True)
                                if payload:
                                    charset = part.get_content_charset() or 'utf-8'
                                    html_body = payload.decode(charset, errors='replace')
                    else:
                        content_type = msg.get_content_type()
                        payload = msg.get_payload(decode=True)
                        if payload:
                            charset = msg.get_content_charset() or 'utf-8'
                            decoded = payload.decode(charset, errors='replace')
                            if content_type == 'text/html':
                                html_body = decoded
                            else:
                                body = decoded
                    
                    # If we only have HTML, convert to clean plain text
                    if not body.strip() and html_body:
                        body = _html_to_text_standalone(html_body)
                    
                    # Clean quoted replies from body
                    if body:
                        body = _clean_email_body_standalone(body)
                    
                    # Extract attachments from the email
                    email_attachments = extract_email_attachments(msg)
                    
                    # Check if this is a reply to an existing ticket
                    existing_ticket = await find_ticket_by_reply_for_account(
                        fresh_db, workspace_id, in_reply_to, references
                    )
                    
                    # If reply belongs to a closed/resolved ticket, skip this email entirely
                    if existing_ticket == 'CLOSED':
                        print(f"[Email Account] ⏭️ SKIPPING: Email is a reply to a closed/resolved ticket")
                        _syslog('INFO', 'Email Account', 'Skipped reply to closed ticket', f'Subject={subject[:80]} | From={sender_email_addr}', workspace_id)
                        processed = ProcessedMail(
                            message_id=message_id,
                            email_from=sender_email_addr or 'unknown@unknown.com',
                            subject=subject,
                            ticket_id=None,
                            workspace_id=workspace_id,
                            email_account=account_email.lower(),
                            processed_at=get_local_time()
                        )
                        fresh_db.add(processed)
                        await fresh_db.commit()
                        if mail:
                            try:
                                def _mark_read_closed(_folder=email_folder, _eid=email_id):
                                    mail.select(_folder)
                                    mail.uid('store', _eid, '+FLAGS', '\\Seen')
                                await asyncio.to_thread(_mark_read_closed)
                            except Exception as e:
                                print(f"[Email Account] Warning: Could not mark email as read: {e}")
                                _syslog('WARNING', 'Email Account', 'Failed to mark email as read', str(e)[:200], workspace_id)
                        continue
                    
                    # If not found via headers, try by sender email
                    # (Skip subject matching - too aggressive, catches invoice numbers etc.)
                    # NEVER use sender fallback for our own address — it has many open
                    # tickets, so it would match everything to one ticket
                    if not existing_ticket and not is_from_self:
                        print(f"[Email Account] Trying sender email fallback...")
                        existing_ticket = await find_ticket_by_sender_for_account(
                            fresh_db, workspace_id, sender_email_addr
                        )
                    elif not existing_ticket and is_from_self:
                        print(f"[Email Account] Skipping sender fallback (email is from our own address)")
                    
                    if existing_ticket:
                        # Refresh the ticket to ensure all attributes are loaded
                        await fresh_db.refresh(existing_ticket)
                        existing_ticket_id = existing_ticket.id
                        existing_ticket_number = existing_ticket.ticket_number
                        
                        print(f"[Email Account] ✅ MATCH FOUND - Adding comment to ticket #{existing_ticket_number}")
                        _syslog('INFO', 'Email Account', f'Matched to ticket #{existing_ticket_number}', f'From={sender_email_addr} | Subject={subject[:80]}', workspace_id)
                        
                        # Add as comment to existing ticket
                        await add_comment_from_email_for_account(
                            fresh_db, existing_ticket, sender_name, sender_email_addr, body,
                            attachments=email_attachments
                        )
                        
                        # Mark email as processed (linked to existing ticket)
                        processed = ProcessedMail(
                            message_id=message_id,
                            email_from=sender_email_addr or 'unknown@unknown.com',
                            subject=subject,
                            ticket_id=existing_ticket_id,
                            workspace_id=workspace_id,
                            email_account=account_email.lower(),
                            processed_at=get_local_time()
                        )
                        fresh_db.add(processed)
                        await fresh_db.commit()
                        
                        # Mark as read (run in thread)
                        if mail:
                            try:
                                # Capture variables by value using default arguments to avoid closure bug
                                def _mark_read_2(_folder=email_folder, _eid=email_id):
                                    mail.select(_folder)
                                    mail.uid('store', _eid, '+FLAGS', '\\Seen')
                                await asyncio.to_thread(_mark_read_2)
                            except Exception as e:
                                print(f"[Email Account] Warning: Could not mark email as read: {e}")
                                _syslog('WARNING', 'Email Account', 'Failed to mark email as read', str(e)[:200], workspace_id)
                        
                        print(f"[Email Account] Added comment to ticket #{existing_ticket_number} from {sender_email_addr}")
                        _syslog('INFO', 'Email Account', f'Comment added to ticket #{existing_ticket_number}', f'From={sender_email_addr}', workspace_id)
                        continue  # Move to next email, don't create new ticket
                    
                    # Safety check: prevent duplicate ticket creation if this Message-ID
                    # was already processed by THIS account and has a ticket.
                    # This catches cases where ProcessedMail records were lost/invalidated.
                    # Per-account only — different accounts create their own tickets.
                    existing_pm = await fresh_db.execute(
                        select(ProcessedMail).where(
                            ProcessedMail.message_id == message_id,
                            ProcessedMail.email_account == account_email.lower(),
                            ProcessedMail.ticket_id.isnot(None)
                        )
                    )
                    already_has_ticket = existing_pm.scalars().first()
                    if already_has_ticket:
                        print(f"[Email Account] ⏭️ SKIPPING: Message-ID already has ticket #{already_has_ticket.ticket_id} in this workspace (safety dedup)")
                        _syslog('INFO', 'Email Account', 'Skipped duplicate Message-ID (safety)', f'From={sender_email_addr} | Subject={subject[:80]} | ExistingTicket={already_has_ticket.ticket_id}', workspace_id)
                        processed = ProcessedMail(
                            message_id=message_id,
                            email_from=sender_email_addr or 'unknown@unknown.com',
                            subject=subject,
                            ticket_id=already_has_ticket.ticket_id,
                            workspace_id=workspace_id,
                            email_account=account_email.lower(),
                            processed_at=get_local_time()
                        )
                        fresh_db.add(processed)
                        await fresh_db.commit()
                        if mail:
                            try:
                                def _mark_read_dedup(_folder=email_folder, _eid=email_id):
                                    mail.select(_folder)
                                    mail.uid('store', _eid, '+FLAGS', '\\Seen')
                                await asyncio.to_thread(_mark_read_dedup)
                            except Exception as e:
                                _syslog('WARNING', 'Email Account', 'Failed to mark email as read', str(e)[:200], workspace_id)
                        continue

                    print(f"[Email Account] ❌ NO MATCH - Creating new ticket")
                    _syslog('INFO', 'Email Account', 'No match - creating new ticket', f'From={sender_email_addr} | Subject={subject[:80]} | InReplyTo={in_reply_to[:60]} | Refs={references[:60]}', workspace_id)
                    
                    # Determine priority
                    # Only check subject for priority keywords (body has too many false matches)
                    subject_lower = subject.lower()
                    urgent_keywords = ['urgent', 'emergency', 'critical', 'asap']
                    high_keywords = ['important', 'high priority']
                    
                    if any(keyword in subject_lower for keyword in urgent_keywords):
                        priority = 'urgent'
                    elif any(keyword in subject_lower for keyword in high_keywords):
                        priority = 'high'
                    else:
                        priority = default_priority
                    
                    # Generate unique ticket number
                    ticket_number = await generate_unique_ticket_number(fresh_db, workspace_id)
                    
                    # Create ticket
                    new_ticket = Ticket(
                        ticket_number=ticket_number,
                        subject=subject[:200],
                        description=body[:5000],
                        priority=priority,
                        status='open',
                        category=default_category,
                        workspace_id=workspace_id,
                        related_project_id=project_id,  # Link to project for this email account
                        created_by_id=None,  # Guest ticket
                        assigned_to_id=auto_assign_to_user_id,  # Auto-assign if configured
                        is_guest=True,
                        guest_name=sender_name.split()[0] if sender_name and sender_name.strip() else "Unknown",
                        guest_surname=sender_name.split()[-1] if sender_name and len(sender_name.split()) > 1 else "",
                        guest_email=sender_email_addr,
                        guest_phone="",
                        guest_company=account_name,  # Use email account name as company
                        guest_branch="",
                        created_at=get_local_time(),
                        updated_at=get_local_time()
                    )
                    
                    fresh_db.add(new_ticket)
                    await fresh_db.flush()
                    
                    # Store ID immediately after flush to avoid lazy loading issues
                    ticket_id = new_ticket.id
                    
                    # Add history entry
                    history = TicketHistory(
                        ticket_id=ticket_id,
                        user_id=None,
                        action='created',
                        new_value=f'Ticket created from email via {account_name}: {sender_email_addr}',
                        created_at=get_local_time()
                    )
                    fresh_db.add(history)
                    
                    # Save email attachments if any
                    if email_attachments:
                        try:
                            await save_email_attachments(fresh_db, ticket_id, email_attachments)
                        except Exception as e:
                            print(f"[Email Attachment] Failed to save attachments for ticket {ticket_id}: {e}")
                            _syslog('ERROR', 'Email Account', 'Attachment save failed', f'Ticket={ticket_id} | Error={str(e)[:200]}', workspace_id)
                    
                    # Mark email as processed
                    processed = ProcessedMail(
                        message_id=message_id,
                        email_from=sender_email_addr or 'unknown@unknown.com',
                        subject=subject,
                        ticket_id=ticket_id,
                        workspace_id=workspace_id,
                        email_account=account_email.lower(),
                        processed_at=get_local_time()
                    )
                    fresh_db.add(processed)
                    await fresh_db.commit()
                    await fresh_db.refresh(new_ticket)
                    
                    # Mark as read (run in thread)
                    if mail:
                        try:
                            # Capture variables by value using default arguments to avoid closure bug
                            def _mark_read_3(_folder=email_folder, _eid=email_id):
                                mail.select(_folder)
                                mail.uid('store', _eid, '+FLAGS', '\\Seen')
                            await asyncio.to_thread(_mark_read_3)
                        except Exception as e:
                            print(f"[Email Account] Warning: Could not mark email as read: {e}")
                            _syslog('WARNING', 'Email Account', 'Failed to mark email as read', str(e)[:200], workspace_id)
                    
                    # Notify all admins and users with can_see_all_tickets permission
                    admin_query = select(User).where(
                        User.workspace_id == workspace_id,
                        User.is_active == True,
                        (User.is_admin == True) | (User.can_see_all_tickets == True)
                    )
                    result = await fresh_db.execute(admin_query)
                    notify_users = result.scalars().all()
                    
                    for user in notify_users:
                        # Check if user has muted ticket notifications
                        if getattr(user, 'mute_ticket_notifications', False):
                            continue
                        notification = Notification(
                            user_id=user.id,
                            message=f"📧 New Ticket: #{ticket_number} - Email from {sender_name} ({sender_email_addr}): {subject[:100]}",
                            type='ticket',
                            url=f'/web/tickets/{ticket_id}',
                            related_id=ticket_id
                        )
                        fresh_db.add(notification)
                    
                    await fresh_db.commit()
                    
                    tickets_created.append(new_ticket)
                    print(f"[Email Account] ✅ Created ticket #{ticket_number} (ID: {ticket_id}) from {sender_email_addr} via {account_name}")
                    _syslog('INFO', 'Email Account', f'Created ticket #{ticket_number}', f'From={sender_email_addr} | Subject={subject[:80]} | MsgID={message_id[:80]}', workspace_id)
                
            except Exception as e:
                err_str = str(e).lower()
                if 'database is locked' in err_str or 'locked' in err_str:
                    print(f"[Email Account] ⚠️ Database locked while processing email {email_id} - will retry next cycle")
                    _syslog('WARNING', 'Email Account', f'Database locked', f'UID={email_id} | Will retry next cycle', workspace_id)
                    break  # Stop processing this batch — DB is unavailable, retrying won't help
                print(f"[Email Account] Error processing email {email_id}: {e}")
                _syslog('ERROR', 'Email Account', f'Error processing email', f'UID={email_id} | Error={str(e)[:200]}', workspace_id)
                import traceback
                traceback.print_exc()
                continue
        
        # Close connection in thread pool (with timeout to prevent hanging)
        if mail:
            try:
                await asyncio.wait_for(
                    asyncio.to_thread(lambda: (mail.close(), mail.logout())),
                    timeout=15
                )
            except (asyncio.TimeoutError, Exception) as e:
                print(f"[Email Account] Warning: IMAP close/logout issue: {e}")
                _syslog('WARNING', 'Email Account', 'IMAP close/logout issue', str(e)[:200], workspace_id)
        if pop3_conn:
            try:
                await asyncio.wait_for(
                    asyncio.to_thread(lambda: pop3_conn.quit()),
                    timeout=15
                )
            except (asyncio.TimeoutError, Exception) as e:
                print(f"[Email Account] Warning: POP3 quit issue: {e}")
                _syslog('WARNING', 'Email Account', 'POP3 quit issue', str(e)[:200], workspace_id)
        
    except Exception as e:
        print(f"[Email Account] ❌ Error fetching emails for account {account_name}: {e}")
        _syslog('ERROR', 'Email Account', f'Error fetching emails for {account_name}', str(e)[:200], workspace_id)
        import traceback
        traceback.print_exc()
        if mail:
            try:
                await asyncio.wait_for(
                    asyncio.to_thread(lambda: (mail.close(), mail.logout())),
                    timeout=15
                )
            except (asyncio.TimeoutError, Exception) as e:
                _syslog('WARNING', 'Email Account', 'IMAP close/logout failed on error path', str(e)[:200], workspace_id)
        if pop3_conn:
            try:
                await asyncio.wait_for(
                    asyncio.to_thread(lambda: pop3_conn.quit()),
                    timeout=15
                )
            except (asyncio.TimeoutError, Exception) as e:
                _syslog('WARNING', 'Email Account', 'POP3 quit failed on error path', str(e)[:200], workspace_id)
        # Re-raise so the caller can report the error per-account
        raise
    
    return tickets_created
