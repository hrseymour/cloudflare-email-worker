#!/usr/bin/env python3
"""
Script to view failed emails stored in Cloudflare R2
Uses boto3 with R2's S3-compatible API

Setup:
  1. pip install boto3
  2. Set environment variables (or use .env file):
     export R2_ACCESS_KEY_ID="your-access-key"
     export R2_SECRET_ACCESS_KEY="your-secret-key"
     export R2_ENDPOINT="https://your-account-id.r2.cloudflarestorage.com"

Usage: python view_failed_emails.py [options]
"""

import argparse
import json
import os
import sys
from email import message_from_string
from email.policy import default
from typing import List, Dict, Any, Optional, Tuple

import boto3
import html2text

# ============================================================================
# CONFIGURATION - Update this section for your setup
# ============================================================================

# R2 bucket name (should match wrangler.toml)
BUCKET_NAME = 'failed-emails'

# Email addresses to filter by (optional)
EMAIL_ADDRESSES = [
    'harlan@harlanseymour.com',
    'test@harlanseymour.com'
]

# R2 credentials (loaded from environment variables)
R2_ACCESS_KEY_ID = os.environ.get('R2_ACCESS_KEY_ID')
R2_SECRET_ACCESS_KEY = os.environ.get('R2_SECRET_ACCESS_KEY')
R2_ENDPOINT = os.environ.get('R2_ENDPOINT')

# ============================================================================
# CONSTANTS
# ============================================================================

# Display constants
SEPARATOR_LENGTH = 70
SEPARATOR_CHAR = '═'
LIST_SEPARATOR_LENGTH = 115

# Content limits
RAW_CONTENT_PREVIEW_LENGTH = 2000
DEFAULT_RECENT_COUNT = 10
CACHE_SIZE_FOR_NUMBERED_ACCESS = 50

# ============================================================================
# SCRIPT CODE - No need to modify below this line
# ============================================================================

def _build_prefix(email_filter: Optional[str]) -> str:
    """Build S3 prefix from email filter."""
    return f'{email_filter.lower()}/' if email_filter else ''


def _print_separator(length: int = SEPARATOR_LENGTH, char: str = SEPARATOR_CHAR) -> None:
    """Print a separator line."""
    print(char * length)


def get_s3_client():
    """Create and return an S3 client configured for R2"""
    if not all([R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ENDPOINT]):
        print("Error: R2 credentials not set!", file=sys.stderr)
        print("\nPlease set these environment variables:", file=sys.stderr)
        print("  export R2_ACCESS_KEY_ID='your-access-key'", file=sys.stderr)
        print("  export R2_SECRET_ACCESS_KEY='your-secret-key'", file=sys.stderr)
        print("  export R2_ENDPOINT='https://your-account-id.r2.cloudflarestorage.com'", file=sys.stderr)
        print("\nOr create a .env file with these values and load it:", file=sys.stderr)
        print("  set -a; source .env; set +a", file=sys.stderr)
        sys.exit(1)

    return boto3.client(
        's3',
        endpoint_url=R2_ENDPOINT,
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        region_name='auto'
    )


def list_objects(prefix: str = '') -> List[Dict[str, Any]]:
    """List all objects in the bucket with given prefix"""
    s3 = get_s3_client()

    try:
        paginator = s3.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=BUCKET_NAME, Prefix=prefix)

        objects = []
        for page in pages:
            if 'Contents' in page:
                objects.extend(page['Contents'])

        return objects
    except Exception as e:
        print(f"Error listing objects: {e}", file=sys.stderr)
        return []


def get_object(key: str) -> Optional[str]:
    """Retrieve an object from R2"""
    s3 = get_s3_client()

    try:
        response = s3.get_object(Bucket=BUCKET_NAME, Key=key)
        return response['Body'].read().decode('utf-8')
    except Exception as e:
        print(f"Error retrieving object: {e}", file=sys.stderr)
        return None


def delete_object(key: str) -> bool:
    """Delete an object from R2"""
    s3 = get_s3_client()

    try:
        s3.delete_object(Bucket=BUCKET_NAME, Key=key)
        return True
    except Exception as e:
        print(f"Error deleting object: {e}", file=sys.stderr)
        return False

def extract_email_body(raw_email: str) -> str:
    """Extract the body content from raw email"""
    try:
        msg = message_from_string(raw_email, policy=default)

        text_body = None
        html_body = None

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                disposition = str(part.get('Content-Disposition'))

                # Skip attachments
                if 'attachment' in disposition:
                    continue

                if content_type == 'text/plain' and not text_body:
                    text_body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                elif content_type == 'text/html' and not html_body:
                    html_body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
        else:
            # Not multipart
            content_type = msg.get_content_type()
            if content_type == 'text/plain':
                text_body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
            elif content_type == 'text/html':
                html_body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')

        # Prefer text, fall back to HTML converted to text
        if text_body:
            return text_body.strip()
        elif html_body:
            # Convert HTML to text
            h = html2text.HTML2Text()
            h.ignore_links = False
            return h.handle(html_body).strip()
        else:
            return "(No text body found)"

    except Exception as e:
        return f"(Error extracting body: {e})"

def list_emails(email_filter: Optional[str] = None) -> None:
    """List all failed emails in R2"""
    prefix = _build_prefix(email_filter)

    if email_filter:
        print(f'\n📧 Listing failed emails for {email_filter}...\n')
    else:
        print('\n📧 Listing all failed emails from R2...\n')

    objects = list_objects(prefix)

    if not objects:
        if email_filter:
            print(f'No failed emails found for {email_filter} in R2.')
        else:
            print('No failed emails found in R2.')
        return

    print(f"Found {len(objects)} email(s):\n")
    print(f"{'Key':<80} {'Size':<10} {'Last Modified':<25}")
    print("=" * LIST_SEPARATOR_LENGTH)

    for obj in objects:
        key = obj['Key']
        size = obj['Size']
        modified = obj['LastModified'].strftime('%Y-%m-%d %H:%M:%S %Z')
        print(f"{key:<80} {size:<10} {modified:<25}")

def get_email(filename: str, full_details: bool = False) -> None:
    """Retrieve and display a specific email"""
    if full_details:
        print(f'\n📧 Retrieving email (full details): {filename}\n')
    else:
        print(f'\n📧 Retrieving email: {filename}\n')

    content = get_object(filename)

    if not content:
        return

    try:
        email_data = json.loads(content)

        _print_separator()
        print('Email Details:')
        _print_separator()
        print(f"From:           {email_data.get('from', 'N/A')}")
        print(f"To:             {email_data.get('to', 'N/A')}")
        print(f"Forward Target: {email_data.get('intendedForwardTo', 'N/A')}")
        print(f"Subject:        {email_data.get('subject', '(No Subject)')}")
        print(f"Timestamp:      {email_data.get('timestamp', 'N/A')}")
        print(f"Size:           {email_data.get('size', 'N/A')} bytes")

        if full_details:
            print(f"Error Reason:   {email_data.get('errorReason', 'N/A')}")

        _print_separator()

        if full_details:
            print('\nHeaders:')
            print(json.dumps(email_data.get('headers', {}), indent=2))

        # Extract and display email body
        raw_content = email_data.get('rawContent', '')
        if raw_content:
            body = extract_email_body(raw_content)
            print('\n', end='')
            _print_separator()
            print('Email Body:')
            _print_separator()
            print(body)
            _print_separator()

            if full_details:
                print('\n', end='')
                _print_separator()
                print(f'Raw Email Content (first {RAW_CONTENT_PREVIEW_LENGTH} characters):')
                _print_separator()
                print(raw_content[:RAW_CONTENT_PREVIEW_LENGTH])
                if len(raw_content) > RAW_CONTENT_PREVIEW_LENGTH:
                    print('\n... (truncated)')
        else:
            print("\n(No email content available)")

        if not full_details:
            print(f"\n💡 Tip: To see full headers, use: --get {filename} --full")

        _print_separator()
        print()

    except json.JSONDecodeError as e:
        print(f"Error parsing email JSON: {e}", file=sys.stderr)

def get_recent_emails(count: int = DEFAULT_RECENT_COUNT, email_filter: Optional[str] = None) -> List[str]:
    """Retrieve and display the most recent failed emails. Returns list of email keys."""
    prefix = _build_prefix(email_filter)

    if email_filter:
        print(f'\n📧 Retrieving {count} most recent failed emails for {email_filter}...\n')
    else:
        print(f'\n📧 Retrieving {count} most recent failed emails...\n')

    objects = list_objects(prefix)

    if not objects:
        if email_filter:
            print(f'No failed emails found for {email_filter} in R2.')
        else:
            print('No failed emails found in R2.')
        return []

    # Filter for JSON files only
    email_files = [obj for obj in objects if obj['Key'].endswith('.json')]

    # Sort by key (which includes timestamp) and take most recent
    email_files = sorted(email_files, key=lambda x: x['Key'], reverse=True)[:count]

    # Build cache for numbered access
    cache = [obj['Key'] for obj in email_files]

    print(f'Found {len(email_files)} recent email(s):\n')

    for index, obj in enumerate(email_files, 1):
        key = obj['Key']
        content = get_object(key)

        if content:
            try:
                email_data = json.loads(content)

                print(f"{index}. {key}")
                print(f"   From:       {email_data.get('from', 'N/A')}")
                print(f"   To:         {email_data.get('to', 'N/A')}")
                print(f"   Forward To: {email_data.get('intendedForwardTo', 'N/A')}")
                print(f"   Subject:    {email_data.get('subject', '(No Subject)')}")
                print(f"   Timestamp:  {email_data.get('timestamp', 'N/A')}")
                print()

            except json.JSONDecodeError:
                print(f"   Error: Could not parse email data")

    print(f'💡 To view email: python view_failed_emails.py --get 1')
    print(f'💡 Or use filename: python view_failed_emails.py --get "<filename>"')

    return cache

def delete_email(filename: str) -> None:
    """Delete a specific email from R2"""
    print(f'\n🗑️  Deleting email: {filename}\n')

    if delete_object(filename):
        print('✓ Email deleted successfully.')
    else:
        print('✗ Failed to delete email.')


def delete_all_emails(email_filter: Optional[str] = None, confirm: bool = True) -> None:
    """Delete all failed emails (with confirmation)"""
    prefix = _build_prefix(email_filter)

    objects = list_objects(prefix)
    email_files = [obj for obj in objects if obj['Key'].endswith('.json')]

    if not email_files:
        print('\nNo emails to delete.')
        return

    print(f'\n⚠️  About to delete {len(email_files)} email(s)')
    if email_filter:
        print(f'   For: {email_filter}')
    else:
        print(f'   For: ALL email addresses')

    if confirm:
        response = input('\nAre you sure? Type "yes" to confirm: ')
        if response.lower() != 'yes':
            print('Cancelled.')
            return

    print(f'\n🗑️  Deleting {len(email_files)} emails...')

    success_count = 0
    for obj in email_files:
        if delete_object(obj['Key']):
            success_count += 1
            print(f'  ✓ Deleted: {obj["Key"]}')
        else:
            print(f'  ✗ Failed: {obj["Key"]}')

    print(f'\n✓ Deleted {success_count} of {len(email_files)} emails')


def show_stats() -> None:
    """Show statistics about failed emails by recipient"""
    print('\n📊 Email Statistics by Recipient\n')
    _print_separator(60)

    for email_addr in EMAIL_ADDRESSES:
        prefix = _build_prefix(email_addr)
        objects = list_objects(prefix)

        # Count only JSON files
        count = len([obj for obj in objects if obj['Key'].endswith('.json')])
        print(f"{email_addr:30} {count:3} failed emails")

def populate_cache_silently(email_filter=None, max_emails=100):
    """Populate the recent emails cache without printing anything"""
    global _recent_emails_cache

    prefix = f'{email_filter.lower()}/' if email_filter else ''
    objects = list_objects(prefix)

    # Filter for JSON files only
    email_files = [obj for obj in objects if obj['Key'].endswith('.json')]

    # Sort by key (which includes timestamp) and take most recent
    email_files = sorted(email_files, key=lambda x: x['Key'], reverse=True)[:max_emails]

    # Populate cache
    _recent_emails_cache = [obj['Key'] for obj in email_files]

def main():
    global _recent_emails_cache
    
    parser = argparse.ArgumentParser(
        description='View failed emails stored in Cloudflare R2',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # View 10 most recent emails (all addresses)
  python view_failed_emails.py --recent 10

  # View recent emails for specific address
  python view_failed_emails.py --recent 5 --email harlan@harlanseymour.com

  # View specific email by number (from recent list)
  python view_failed_emails.py --get 1

  # View specific email by filename
  python view_failed_emails.py --get "harlan@harlanseymour.com/2024-10-10T..."

  # View with full details (headers + raw content)
  python view_failed_emails.py --get 1 --full

  # Show statistics
  python view_failed_emails.py --stats

  # Delete specific email
  python view_failed_emails.py --delete 1

  # Delete all emails (with confirmation)
  python view_failed_emails.py --delete-all

  # Delete all for specific address
  python view_failed_emails.py --delete-all --email harlan@harlanseymour.com

Setup:
  1. Install boto3: pip install boto3 html2text
  2. Set environment variables with your R2 credentials:
     export R2_ACCESS_KEY_ID='your-access-key'
     export R2_SECRET_ACCESS_KEY='your-secret-key'
     export R2_ENDPOINT='https://your-account-id.r2.cloudflarestorage.com'
        """
    )

    parser.add_argument('--list', action='store_true',
                       help='List all failed emails with metadata')
    parser.add_argument('--get', type=str, metavar='NUMBER_OR_FILENAME',
                       help='View email by number (from recent list) or filename')
    parser.add_argument('--recent', type=int, nargs='?', const=DEFAULT_RECENT_COUNT, metavar='N',
                       help=f'Show N most recent failed emails (default: {DEFAULT_RECENT_COUNT})')
    parser.add_argument('--delete', type=str, metavar='NUMBER_OR_FILENAME',
                       help='Delete email by number or filename')
    parser.add_argument('--delete-all', action='store_true',
                       help='Delete all failed emails (requires confirmation)')
    parser.add_argument('--email', type=str, metavar='ADDRESS',
                       help='Filter by recipient email address')
    parser.add_argument('--stats', action='store_true',
                       help='Show statistics by email address')
    parser.add_argument('--full', action='store_true',
                       help='Show full details including headers and raw content')
    parser.add_argument('--yes', action='store_true',
                       help='Skip confirmation prompts (for --delete-all)')

    return parser


def main() -> None:
    """Main entry point for the script"""
    parser = _create_argument_parser()
    args = parser.parse_args()
    
    # Handle numbered --get (populate cache silently with smart loading)
    if args.get and args.get.isdigit():
        # Smart loading: only load as many as needed, plus a small buffer
        requested_num = int(args.get)
        load_count = requested_num + 10  # Buffer of 10 for convenience

        # Silently populate cache without printing
        populate_cache_silently(args.email, max_emails=load_count)
        
        index = requested_num - 1
        if 0 <= index < len(_recent_emails_cache):
            filename = _recent_emails_cache[index]
            if args.full:
                get_email_full(filename)
            else:
                get_email(filename)
        else:
            print(f"Error: Invalid number {args.get}. Only {len(_recent_emails_cache)} emails available.", file=sys.stderr)
        return
    
    # Handle numbered --delete (populate cache silently with smart loading)
    if args.delete and args.delete.isdigit():
        # Smart loading: only load as many as needed, plus a small buffer
        requested_num = int(args.delete)
        load_count = requested_num + 10  # Buffer of 10 for convenience

        # Silently populate cache without printing
        populate_cache_silently(args.email, max_emails=load_count)
        
        index = requested_num - 1
        if 0 <= index < len(_recent_emails_cache):
            filename = _recent_emails_cache[index]
            delete_email(filename)
        else:
            print(f"Error: Invalid number {args.delete}. Only {len(_recent_emails_cache)} emails available.", file=sys.stderr)
        return

    # Execute the requested action
    if args.delete_all:
        delete_all_emails(args.email, confirm=not args.yes)
    elif args.stats:
        show_stats()
    elif args.list:
        list_emails(args.email)
    elif args.get:
        get_email(args.get, args.full)
    elif args.delete:
        delete_email(args.delete)
    elif args.recent is not None:
        get_recent_emails(args.recent, args.email)
    else:
        # Default: show recent emails
        get_recent_emails(DEFAULT_RECENT_COUNT, args.email)


if __name__ == '__main__':
    main()