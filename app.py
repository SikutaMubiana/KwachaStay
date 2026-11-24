from flask import Flask, Response, abort, render_template, request, redirect, url_for, g, flash, session, jsonify
import sqlite3
import os
import uuid
import secrets
import time
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import functools
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import threading
import calendar
import math
import json
import hmac
import hashlib
import base64
import struct
import re
import urllib.parse
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from dotenv import load_dotenv
from werkzeug.middleware.proxy_fix import ProxyFix
from upload_storage import LocalUploadStorage
from supabase_storage import SupabaseUploadStorage
from database import DB_ERRORS, DB_INTEGRITY_ERRORS, connect as connect_postgres
import phonenumbers

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
APP_ENV = os.getenv('APP_ENV', os.getenv('FLASK_ENV', 'development')).strip().lower()
SECRET_KEY = os.getenv('SECRET_KEY', '').strip()
if APP_ENV == 'production' and not SECRET_KEY:
    raise RuntimeError('SECRET_KEY must be configured when APP_ENV=production.')
app.secret_key = SECRET_KEY or secrets.token_hex(32)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=APP_ENV == 'production',
    SESSION_COOKIE_SAMESITE='Lax',
    PREFERRED_URL_SCHEME='https' if APP_ENV == 'production' else 'http',
    PERMANENT_SESSION_LIFETIME=timedelta(days=7),
    SESSION_REFRESH_EACH_REQUEST=True,
)
SESSION_IDLE_TIMEOUT_SECONDS = max(300, int(os.getenv('SESSION_IDLE_TIMEOUT_SECONDS', '7200')))
ADMIN_SESSION_IDLE_TIMEOUT_SECONDS = max(300, int(os.getenv('ADMIN_SESSION_IDLE_TIMEOUT_SECONDS', '3600')))
RATELIMIT_ENABLED = os.getenv('RATELIMIT_ENABLED', '1').strip().lower() not in {'0', 'false', 'no', 'off'}
MAX_IMAGE_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB per uploaded image file
if APP_ENV == 'production':
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, 'kwachastay.db')
BOOKING_SERVICE_FEE = 50
BOOKING_REQUEST_EXPIRY_HOURS = max(1, min(168, int(os.getenv('BOOKING_REQUEST_EXPIRY_HOURS', '24'))))
FLUTTERWAVE_SECRET_KEY = os.getenv('FLUTTERWAVE_SECRET_KEY', '').strip()
FLUTTERWAVE_SECRET_HASH = os.getenv('FLUTTERWAVE_SECRET_HASH', '').strip()
PUBLIC_BASE_URL = (
    os.getenv('PUBLIC_BASE_URL', '').strip()
    or os.getenv('RENDER_EXTERNAL_URL', '').strip()
).rstrip('/')
DATABASE_URL = os.getenv('DATABASE_URL', '').strip()
ADMIN_EMAILS = {
    email.strip().lower()
    for email in os.getenv('ADMIN_EMAILS', '').split(',')
    if email.strip()
}
_configured_storage = os.getenv('STORAGE_BACKEND', '').strip().lower()
if _configured_storage:
    STORAGE_BACKEND = _configured_storage
elif os.getenv('SUPABASE_URL', '').strip() and os.getenv('SUPABASE_SERVICE_ROLE_KEY', '').strip():
    STORAGE_BACKEND = 'supabase'
else:
    STORAGE_BACKEND = 'local'
EMAIL_PROVIDER = os.getenv('EMAIL_PROVIDER', 'resend').strip().lower()
RESEND_API_KEY = os.getenv('RESEND_API_KEY', '').strip()
RESEND_FROM_EMAIL = os.getenv('RESEND_FROM_EMAIL', '').strip()
RESEND_WEBHOOK_SECRET = os.getenv('RESEND_WEBHOOK_SECRET', '').strip()
EMAIL_VERIFICATION_TTL_SECONDS = max(900, int(os.getenv('EMAIL_VERIFICATION_TTL_SECONDS', '86400')))
PASSWORD_RESET_TTL_SECONDS = max(900, int(os.getenv('PASSWORD_RESET_TTL_SECONDS', '3600')))
EMAIL_WEBHOOK_MAX_AGE_SECONDS = max(60, int(os.getenv('EMAIL_WEBHOOK_MAX_AGE_SECONDS', '300')))
BANK_TRANSFER_DETAILS = {
    'bank_name': os.getenv('BANK_TRANSFER_BANK_NAME', '').strip(),
    'account_name': os.getenv('BANK_TRANSFER_ACCOUNT_NAME', '').strip(),
    'account_number': os.getenv('BANK_TRANSFER_ACCOUNT_NUMBER', '').strip(),
    'branch': os.getenv('BANK_TRANSFER_BRANCH', '').strip(),
    'swift_code': os.getenv('BANK_TRANSFER_SWIFT_CODE', '').strip(),
}
BANK_TRANSFER_ENABLED = all(
    BANK_TRANSFER_DETAILS[key] for key in ('bank_name', 'account_name', 'account_number')
)
PAYMENT_WHATSAPP_NUMBER = '260764483750'
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID', '').strip()
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN', '').strip()
TWILIO_FROM_NUMBER = os.getenv('TWILIO_FROM_NUMBER', '').strip()
_last_booking_expiry_sweep = 0
_booking_expiry_sweep_lock = threading.Lock()
LUSAKA_NEIGHBOURHOODS = sorted([
    'Avondale',
    'Barlastone',
    'Bauleni',
    'Chaisa',
    'Chalala',
    'Chamba Valley',
    'Chainda',
    'Chazanga',
    'Chawama',
    'Chelstone',
    'Chibolya',
    'Chilenje',
    'Chilenje South',
    'Chinika',
    'Chunga',
    'Emmasdale',
    'Foxdale',
    'Garden',
    'Garden House',
    'George',
    'Ibex Hill',
    'Jack Compound',
    'Jesmondine',
    'John Laing',
    'Kabwata',
    'Kabulonga',
    'Kabanana',
    'Kalingalinga',
    'Kalikiliki',
    'Kalundu',
    'Kamanga',
    'Kamwala',
    'Kamwala South',
    'Kanyama',
    'Kaunda Square',
    'Libala',
    'Libala South',
    'Lilanda',
    'Lilayi',
    'Linda',
    'Longacres',
    'Makeni',
    'Makeni Bonaventure',
    'Makeni Villa',
    'Mandevu',
    'Marapodi',
    'Mass Media',
    'Matero',
    'Meanwood',
    'Meanwood Chamba Valley',
    'Meanwood Ibex',
    'Meanwood Kwamwena',
    'Meanwood Ndeke',
    'Mazyopa',
    'Mtendere',
    'Munali',
    'New Kasama',
    "Ng'ombe",
    'Northmead',
    'Olympia',
    'Olympia Park',
    'Olympia Extension',
    'PHI',
    'Rhodes Park',
    'Roma',
    'Salama Park',
    'Showgrounds',
    'Sikanze',
    'State Lodge',
    'Sunningdale',
    'Thorn Park',
    'Twin Palm',
    'Woodlands',
    'Woodlands Extension',
    'Zingalume',
])
LUSAKA_DEFAULT_COORDS = (-15.4167, 28.2833)
LUSAKA_NEIGHBOURHOOD_COORDS = {
    'Avondale': (-15.3886, 28.3935),
    'Barlastone': (-15.3520, 28.2345),
    'Bauleni': (-15.4586, 28.3612),
    'Chaisa': (-15.3745, 28.2845),
    'Chalala': (-15.4685, 28.3485),
    'Chamba Valley': (-15.3490, 28.3525),
    'Chainda': (-15.3945, 28.4195),
    'Chazanga': (-15.3350, 28.2890),
    'Chawama': (-15.4580, 28.2735),
    'Chelstone': (-15.3755, 28.3835),
    'Chibolya': (-15.4325, 28.2685),
    'Chilenje': (-15.4485, 28.3275),
    'Chilenje South': (-15.4615, 28.3285),
    'Chinika': (-15.4150, 28.2485),
    'Chunga': (-15.3480, 28.2575),
    'Emmasdale': (-15.3895, 28.2815),
    'Foxdale': (-15.3595, 28.3345),
    'Garden': (-15.3895, 28.2995),
    'Garden House': (-15.3975, 28.2195),
    'George': (-15.3675, 28.2455),
    'Ibex Hill': (-15.4325, 28.3745),
    'Jack Compound': (-15.4685, 28.2995),
    'Jesmondine': (-15.3835, 28.3465),
    'John Laing': (-15.4455, 28.2685),
    'Kabwata': (-15.4395, 28.3085),
    'Kabulonga': (-15.4245, 28.3525),
    'Kabanana': (-15.3325, 28.3095),
    'Kalingalinga': (-15.4055, 28.3495),
    'Kalikiliki': (-15.4045, 28.3685),
    'Kalundu': (-15.3875, 28.3245),
    'Kamanga': (-15.3725, 28.3645),
    'Kamwala': (-15.4295, 28.2895),
    'Kamwala South': (-15.4555, 28.2985),
    'Kanyama': (-15.4345, 28.2505),
    'Kaunda Square': (-15.3735, 28.3545),
    'Libala': (-15.4525, 28.3145),
    'Libala South': (-15.4695, 28.3195),
    'Lilanda': (-15.3735, 28.2515),
    'Lilayi': (-15.5055, 28.2915),
    'Linda': (-15.4895, 28.2795),
    'Longacres': (-15.4145, 28.3115),
    'Makeni': (-15.4685, 28.2535),
    'Makeni Bonaventure': (-15.4865, 28.2485),
    'Makeni Villa': (-15.4595, 28.2615),
    'Mandevu': (-15.3675, 28.2825),
    'Marapodi': (-15.3645, 28.2925),
    'Mass Media': (-15.4025, 28.3345),
    'Matero': (-15.3765, 28.2655),
    'Meanwood': (-15.3395, 28.3685),
    'Meanwood Chamba Valley': (-15.3445, 28.3625),
    'Meanwood Ibex': (-15.4395, 28.3995),
    'Meanwood Kwamwena': (-15.3245, 28.3745),
    'Meanwood Ndeke': (-15.3395, 28.4315),
    'Mazyopa': (-15.3495, 28.2965),
    'Mtendere': (-15.4065, 28.3735),
    'Munali': (-15.3835, 28.3595),
    'New Kasama': (-15.4795, 28.4045),
    "Ng'ombe": (-15.3675, 28.3155),
    'Northmead': (-15.3995, 28.2985),
    'Olympia': (-15.3965, 28.3145),
    'Olympia Park': (-15.3945, 28.3175),
    'Olympia Extension': (-15.3895, 28.3195),
    'PHI': (-15.3885, 28.3685),
    'Rhodes Park': (-15.4105, 28.3035),
    'Roma': (-15.3725, 28.3295),
    'Salama Park': (-15.3845, 28.3975),
    'Showgrounds': (-15.4055, 28.3185),
    'Sikanze': (-15.4315, 28.2975),
    'State Lodge': (-15.4585, 28.4295),
    'Sunningdale': (-15.4275, 28.3415),
    'Thorn Park': (-15.4025, 28.2885),
    'Twin Palm': (-15.4425, 28.3765),
    'Woodlands': (-15.4425, 28.3425),
    'Woodlands Extension': (-15.4495, 28.3545),
    'Zingalume': (-15.3615, 28.2485),
}


def get_neighbourhood_coordinates(compound):
    if not compound:
        return LUSAKA_DEFAULT_COORDS
    if compound in LUSAKA_NEIGHBOURHOOD_COORDS:
        return LUSAKA_NEIGHBOURHOOD_COORDS[compound]
    needle = compound.strip().casefold()
    for name, coords in LUSAKA_NEIGHBOURHOOD_COORDS.items():
        if name.casefold() == needle:
            return coords
    return LUSAKA_DEFAULT_COORDS


def extract_google_maps_coordinates(text):
    raw = (text or '').strip()
    if not raw:
        return None
    patterns = (
        r'@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)',
        r'[?&](?:q|ll|destination|viewpoint)=(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)',
        r'!3d(-?\d+(?:\.\d+)?)!4d(-?\d+(?:\.\d+)?)',
        r'^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$',
    )
    for pattern in patterns:
        match = re.search(pattern, raw)
        if match:
            try:
                lat = float(match.group(1))
                lng = float(match.group(2))
            except ValueError:
                continue
            if -90 <= lat <= 90 and -180 <= lng <= 180:
                return (round(lat, 6), round(lng, 6))
    return None
LUSAKA_AREA_GUIDE = [
    {
        'name': 'Kabulonga',
        'overview': 'A well-established residential area in eastern Lusaka, with homes, restaurants, and everyday services spread along its main roads.',
        'good_for': 'Guests looking for a residential base with dining and services nearby.',
        'tip': 'Ask the host which road or landmark is closest; the area covers a broad stretch.',
    },
    {
        'name': 'Rhodes Park',
        'overview': 'A central residential neighbourhood with convenient access to offices, shops, and services in the surrounding city centre.',
        'good_for': 'Guests who want a central base for business or city visits.',
        'tip': 'Confirm parking and likely travel times for your specific destinations.',
    },
    {
        'name': 'Woodlands',
        'overview': 'A large residential area with shopping and services nearby, and a mix of quieter streets and busy commercial roads.',
        'good_for': 'Guests seeking a residential stay with practical amenities close by.',
        'tip': 'Check the exact location, since properties can be some distance apart.',
    },
    {
        'name': 'Longacres',
        'overview': 'A central district with residential accommodation alongside offices, hotels, and other city services.',
        'good_for': 'Work trips and guests who value access to central Lusaka.',
        'tip': 'Ask whether the property is on a busy road if noise is a concern.',
    },
    {
        'name': 'Ibex Hill',
        'overview': 'A growing residential area in the eastern part of Lusaka, with housing developments and shopping options.',
        'good_for': 'Guests looking for a residential stay in eastern Lusaka.',
        'tip': 'Check distances to your planned destinations before booking.',
    },
    {
        'name': 'Avondale',
        'overview': 'A residential neighbourhood in north-eastern Lusaka, with local shopping and services in the wider area.',
        'good_for': 'Guests visiting the north-eastern side of the city.',
        'tip': 'Confirm the nearest main road or landmark with your host.',
    },
    {
        'name': 'Chelstone',
        'overview': 'A sizeable residential neighbourhood in eastern Lusaka with local shops and community services.',
        'good_for': 'Guests whose plans are centred in eastern Lusaka.',
        'tip': 'The neighbourhood is broad; ask for directions and transport options.',
    },
    {
        'name': 'Chilenje',
        'overview': 'An established residential neighbourhood south of the city centre, with local markets and everyday services.',
        'good_for': 'Guests looking for a lived-in neighbourhood and local amenities.',
        'tip': 'Ask your host about nearby shops and the best route for your plans.',
    },
    {
        'name': 'New Kasama',
        'overview': 'A newer residential area in the southern part of Lusaka, with developing housing and services.',
        'good_for': 'Guests who prefer a more residential setting in southern Lusaka.',
        'tip': 'Check how close the listing is to shops and public transport.',
    },
    {
        'name': 'Roma',
        'overview': 'A residential area in northern Lusaka, with homes and services connected to the wider northern side of the city.',
        'good_for': 'Guests visiting northern Lusaka or nearby institutions and businesses.',
        'tip': 'Confirm the specific location and transport arrangements with your host.',
    },
]
PHOTO_CATEGORIES = {
    'bedroom': 'Bedroom',
    'bathroom': 'Bathroom',
    'kitchen': 'Kitchen',
    'entrance': 'Entrance',
    'parking': 'Parking',
    'living_area': 'Living area',
    'other': 'Other',
}
SUPPORT_CATEGORIES = {
    'listing_issue': 'Misleading or incorrect listing',
    'arrival_issue': 'Check-in or arrival problem',
    'payment_issue': 'Payment problem',
    'refund_issue': 'Refund request or delay',
    'safety_concern': 'Safety concern',
    'other': 'Other',
}
POWER_BACKUP_OPTIONS = {
    'grid_only': 'Grid power only',
    'solar_backup': 'Solar backup',
    'generator_backup': 'Generator backup',
    'solar_and_generator': 'Solar and generator backup',
    'other': 'Other backup',
}
WATER_SUPPLY_OPTIONS = {
    'municipal': 'Municipal supply',
    'borehole': 'Borehole',
    'municipal_and_borehole': 'Municipal and borehole',
    'storage_tank': 'Storage tank',
    'other': 'Other',
}
INTERNET_OPTIONS = {
    'reliable_wifi': 'Wi-Fi (host reports it is reliable)',
    'variable_wifi': 'Wi-Fi (may be variable)',
    'mobile_data': 'Mobile data available',
    'no_internet': 'No internet',
}
SELF_CHECKIN_OPTIONS = {
    'host_meet': 'Meet the host',
    'key_box': 'Key box',
    'smart_lock': 'Smart lock',
    'reception': 'Reception desk',
}
# --- File Upload Config ---
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'jfif', 'gif', 'webp'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max
if STORAGE_BACKEND == 'supabase':
    upload_storage = SupabaseUploadStorage()
elif STORAGE_BACKEND == 'local':
    upload_storage = LocalUploadStorage(UPLOAD_FOLDER)
else:
    raise RuntimeError('STORAGE_BACKEND must be either "local" or "supabase".')
app.config['UPLOADS_ENABLED'] = STORAGE_BACKEND == 'supabase' or APP_ENV != 'production'

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


_IMAGE_MIME_BY_FORMAT = {
    'png': ('png', 'image/png'),
    'jpeg': ('jpg', 'image/jpeg'),
    'gif': ('gif', 'image/gif'),
    'webp': ('webp', 'image/webp'),
}
_EXT_TO_IMAGE_FORMAT = {
    'png': 'png',
    'jpg': 'jpeg',
    'jpeg': 'jpeg',
    'jfif': 'jpeg',
    'gif': 'gif',
    'webp': 'webp',
}
_DISALLOWED_UPLOAD_SNIPPETS = (
    b'<?php', b'<script', b'<svg', b'<!doctype html', b'<html', b'javascript:',
)


def detect_image_format(header_bytes):
    if len(header_bytes) >= 16 and header_bytes.startswith(b'\x89PNG\r\n\x1a\n') and header_bytes[12:16] == b'IHDR':
        return 'png'
    if len(header_bytes) >= 3 and header_bytes.startswith(b'\xff\xd8\xff'):
        return 'jpeg'
    if len(header_bytes) >= 6 and header_bytes[:6] in (b'GIF87a', b'GIF89a'):
        return 'gif'
    if len(header_bytes) >= 12 and header_bytes[:4] == b'RIFF' and header_bytes[8:12] == b'WEBP':
        return 'webp'
    return None


def validate_image_upload(file_storage, max_bytes=MAX_IMAGE_UPLOAD_BYTES):
    """Validate uploaded image extension, size, and actual file magic bytes.

    Accepts genuine PNG/JPEG/GIF/WebP files (even when a browser or phone saved
    them under another allowed image extension like .jpg for WebP) and returns
    the verified (canonical_ext, canonical_mime) derived from the actual bytes.
    """
    filename = (getattr(file_storage, 'filename', None) or '').strip()
    if not filename or not allowed_file(filename):
        raise ValueError('Only PNG, JPG, JPEG, GIF, and WebP images are allowed.')

    stream = file_storage.stream
    if hasattr(stream, 'seek'):
        stream.seek(0)
    data = stream.read(max_bytes + 1)
    if hasattr(stream, 'seek'):
        stream.seek(0)

    if not data:
        raise ValueError('Uploaded file is empty.')
    if len(data) > max_bytes:
        raise ValueError(f'Image must be smaller than {max_bytes // (1024 * 1024)} MB.')

    detected_format = detect_image_format(data[:32])
    if not detected_format:
        raise ValueError('File content is not a valid PNG, JPEG, GIF, or WebP image.')

    leading_lower = data[:512].lower()
    if any(snippet in leading_lower for snippet in _DISALLOWED_UPLOAD_SNIPPETS):
        raise ValueError('Uploaded file contains disallowed active content.')

    return _IMAGE_MIME_BY_FORMAT[detected_format]


def validate_password_strength(password):
    """Enforce consistent password strength rules across signup, reset, and change."""
    if not password or len(password) < 8:
        return 'Password must be at least 8 characters and contain both letters and numbers.'
    if len(password) > 128:
        return 'Password must be 128 characters or fewer.'
    if not (re.search(r'[a-zA-Z]', password) and re.search(r'[0-9]', password)):
        return 'Password must be at least 8 characters and contain both letters and numbers.'
    return None


def validate_image_url(value, allow_empty=False):
    """Allow only safe relative /static/uploads/ paths or https:// URLs."""
    url = (value or '').strip()
    if not url:
        if allow_empty:
            return ''
        raise ValueError('Please provide a valid image URL.')
    if len(url) > 2000 or any(ch in url for ch in ('"', "'", '<', '>', '\r', '\n', '\x00')):
        raise ValueError('Invalid image URL.')
    if url.startswith('/static/uploads/') and '..' not in url:
        return url
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme == 'https' and parsed.hostname:
        return url
    raise ValueError('Image URLs must use HTTPS or an uploaded KwachaStay photo.')


def safe_redirect_referrer(fallback_endpoint, **values):
    referrer = request.referrer
    if referrer:
        parsed = urllib.parse.urlsplit(referrer)
        if parsed.netloc == request.host and parsed.scheme in ('http', 'https'):
            target = parsed.path or '/'
            if parsed.query:
                target += f'?{parsed.query}'
            return redirect(target)
    return redirect(url_for(fallback_endpoint, **values))


def client_ip():
    return (request.remote_addr or 'unknown')[:64]


def check_rate_limit(action, rate_key, limit, window_seconds):
    """Fixed-window DB-backed rate limiter shared across Gunicorn workers."""
    if not RATELIMIT_ENABLED:
        return True
    return email_rate_limit(action, rate_key, limit, window_seconds)


def is_rate_limited(action, rate_key, limit, window_seconds):
    if not RATELIMIT_ENABLED:
        return False
    now = time.time()
    db = get_db()
    row = db.execute(
        'SELECT window_started, request_count FROM email_rate_limits WHERE action = ? AND rate_key = ?',
        (action, rate_key),
    ).fetchone()
    if not row or now - row['window_started'] >= window_seconds:
        return False
    return row['request_count'] >= limit


def record_rate_limit_hit(action, rate_key, window_seconds):
    if not RATELIMIT_ENABLED:
        return
    now = time.time()
    db = get_db()
    row = db.execute(
        'SELECT window_started, request_count FROM email_rate_limits WHERE action = ? AND rate_key = ?',
        (action, rate_key),
    ).fetchone()
    if not row or now - row['window_started'] >= window_seconds:
        db.execute(
            '''INSERT INTO email_rate_limits (action, rate_key, window_started, request_count)
               VALUES (?, ?, ?, 1)
               ON CONFLICT(action, rate_key) DO UPDATE SET window_started = excluded.window_started,
               request_count = excluded.request_count''',
            (action, rate_key, now),
        )
    else:
        db.execute(
            'UPDATE email_rate_limits SET request_count = request_count + 1 WHERE action = ? AND rate_key = ?',
            (action, rate_key),
        )
    db.commit()


def reset_rate_limit(action, rate_key):
    db = get_db()
    db.execute(
        'DELETE FROM email_rate_limits WHERE action = ? AND rate_key = ?',
        (action, rate_key),
    )
    db.commit()


def log_admin_action(db, action, target_type=None, target_id=None, details=None, admin_user=None):
    """Record an administrative action in admin_audit_logs (never logs secrets)."""
    actor = admin_user or getattr(g, 'user', None)
    admin_id = actor['id'] if actor else None
    admin_email = actor['email'] if actor else None
    ip_addr = client_ip() if request else None
    safe_details = str(details)[:500] if details is not None else None
    safe_target_id = str(target_id)[:64] if target_id is not None else None
    try:
        db.execute(
            '''INSERT INTO admin_audit_logs
               (admin_id, admin_email, action, target_type, target_id, details, ip_address)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (admin_id, admin_email, action[:80], target_type, safe_target_id, safe_details, ip_addr),
        )
    except DB_ERRORS:
        app.logger.warning('Could not record admin audit log for action %s.', action)


# --- RFC 6238 TOTP (Admin 2FA, zero external dependencies) ---
def generate_totp_secret():
    return base64.b32encode(secrets.token_bytes(20)).decode('ascii').rstrip('=')


def _totp_code_for_counter(secret, counter, digits=6):
    padded = secret.strip().upper().replace(' ', '')
    padded += '=' * ((8 - len(padded) % 8) % 8)
    key = base64.b32decode(padded, casefold=True)
    msg = struct.pack('>Q', int(counter))
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code_int = struct.unpack('>I', digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return f'{code_int % (10 ** digits):0{digits}d}'


def totp_code(secret, for_time=None, step=30, digits=6):
    ts = time.time() if for_time is None else float(for_time)
    return _totp_code_for_counter(secret, int(ts // step), digits=digits)


def verify_totp_code(secret, code, window=1, step=30, digits=6, for_time=None):
    cleaned = re.sub(r'\s+', '', code or '')
    if not secret or not re.fullmatch(rf'\d{{{digits}}}', cleaned):
        return False
    ts = time.time() if for_time is None else float(for_time)
    current_counter = int(ts // step)
    try:
        for delta in range(-window, window + 1):
            expected = _totp_code_for_counter(secret, current_counter + delta, digits=digits)
            if hmac.compare_digest(expected, cleaned):
                return True
    except (ValueError, TypeError):
        return False
    return False


def build_otpauth_uri(email, secret, issuer='KwachaStay'):
    label = urllib.parse.quote(f'{issuer}:{email}')
    params = urllib.parse.urlencode({
        'secret': secret,
        'issuer': issuer,
        'algorithm': 'SHA1',
        'digits': 6,
        'period': 30,
    })
    return f'otpauth://totp/{label}?{params}'


def csp_nonce():
    nonce = getattr(g, 'csp_nonce', None)
    if not nonce:
        nonce = secrets.token_urlsafe(16)
        g.csp_nonce = nonce
    return nonce


def _user_session_version(user_row):
    try:
        value = user_row['session_version']
        return int(value) if value is not None else 1
    except (KeyError, IndexError, TypeError, ValueError):
        return 1


def _user_totp_enabled(user_row):
    try:
        return bool(user_row['totp_enabled']) and bool(user_row['totp_secret'])
    except (KeyError, IndexError):
        return False


def phone_country_options():
    regions = {
        region
        for region in phonenumbers.SUPPORTED_REGIONS
        if region and region != '001'
    }
    return [
        {
            'region': region,
            'calling_code': phonenumbers.country_code_for_region(region),
        }
        for region in sorted(regions)
        if phonenumbers.country_code_for_region(region)
    ]


def normalize_phone_number(value, region=None):
    value = (value or '').strip()
    if not value:
        raise ValueError('Enter your phone number.')
    try:
        parsed = phonenumbers.parse(value, None if value.startswith('+') else region)
    except phonenumbers.NumberParseException as error:
        raise ValueError('Enter a valid phone number and country.') from error
    if not phonenumbers.is_valid_number(parsed):
        raise ValueError('Enter a valid phone number for the selected country.')
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


def token_digest(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def email_delivery_configured():
    if EMAIL_PROVIDER == 'resend':
        return bool(RESEND_API_KEY and RESEND_FROM_EMAIL)
    if EMAIL_PROVIDER == 'smtp':
        return bool(
            os.getenv('MAIL_SERVER', '').strip()
            and os.getenv('MAIL_USERNAME', '').strip()
            and os.getenv('MAIL_PASSWORD', '')
            and (os.getenv('MAIL_DEFAULT_SENDER', '').strip() or os.getenv('MAIL_USERNAME', '').strip())
        )
    return False


def parse_iso_date(value):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def parse_nonnegative_money(value, field_name):
    try:
        amount = float(value or 0)
    except (TypeError, ValueError):
        raise ValueError(f'{field_name} must be a valid amount.')
    if not math.isfinite(amount) or amount < 0:
        raise ValueError(f'{field_name} cannot be negative.')
    return round(amount, 2)


def parse_location_coordinates(latitude_value, longitude_value):
    latitude_value = (latitude_value or '').strip()
    longitude_value = (longitude_value or '').strip()
    if not latitude_value and not longitude_value:
        return None, None
    try:
        latitude = float(latitude_value)
        longitude = float(longitude_value)
    except ValueError:
        raise ValueError('Enter valid coordinates or choose a point on the map.')
    if not math.isfinite(latitude) or not math.isfinite(longitude):
        raise ValueError('Coordinates must be valid numbers.')
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError('Latitude must be between -90 and 90 and longitude between -180 and 180.')
    return latitude, longitude


def parse_property_utility_fields(form):
    fields = {
        'power_backup': (form.get('power_backup', '').strip(), POWER_BACKUP_OPTIONS),
        'water_supply': (form.get('water_supply', '').strip(), WATER_SUPPLY_OPTIONS),
        'internet_availability': (form.get('internet_availability', '').strip(), INTERNET_OPTIONS),
    }
    for field_name, (value, choices) in fields.items():
        if value and value not in choices:
            raise ValueError('Choose valid power, water, and internet options.')

    speed_value = form.get('internet_speed_mbps', '').strip()
    try:
        internet_speed_mbps = int(speed_value) if speed_value else None
    except ValueError:
        raise ValueError('Internet speed must be a whole number between 1 and 1000 Mbps.')
    if internet_speed_mbps is not None and not 1 <= internet_speed_mbps <= 1000:
        raise ValueError('Internet speed must be between 1 and 1000 Mbps.')

    emergency_contact_name = form.get('emergency_contact_name', '').strip()
    emergency_contact_phone = form.get('emergency_contact_phone', '').strip()
    if bool(emergency_contact_name) != bool(emergency_contact_phone):
        raise ValueError('Enter both emergency contact name and phone, or leave both blank.')
    if len(emergency_contact_name) > 100 or len(emergency_contact_phone) > 40:
        raise ValueError('Emergency contact name or phone is too long.')

    return {
        'power_backup': fields['power_backup'][0] or None,
        'water_supply': fields['water_supply'][0] or None,
        'internet_availability': fields['internet_availability'][0] or None,
        'internet_speed_mbps': internet_speed_mbps,
        'emergency_contact_name': emergency_contact_name or None,
        'emergency_contact_phone': emergency_contact_phone or None,
    }


def default_price_period_for_type(property_type):
    if (property_type or '').strip() in ('House', 'Boarding House'):
        return 'month'
    return 'night'


MIN_HOURLY_STAY_HOURS = 3
MAX_HOURLY_STAY_HOURS = 24
UPFRONT_MONTH_OPTIONS = (1, 2, 3, 4, 5, 6, 12)
ROOM_SHARING_OPTIONS = {
    'single': 'Single Room (Private)',
    'shared': 'Shared Room',
}


def supports_hourly_booking(property_row):
    if not property_row:
        return False
    return property_row['price_period'] != 'month'


def get_effective_hourly_rate(property_row):
    raw_hourly = property_row['hourly_rate'] if 'hourly_rate' in property_row.keys() else None
    if raw_hourly is not None and float(raw_hourly) > 0:
        return round(float(raw_hourly), 2)
    return round(max(1.0, float(property_row['price_per_night']) / 8.0), 2)


def get_upfront_months(property_row):
    raw = property_row['upfront_months'] if 'upfront_months' in property_row.keys() else 1
    try:
        val = int(raw or 1)
    except (TypeError, ValueError):
        val = 1
    return max(1, min(val, 24))


def parse_stay_terms_fields(form, property_type, price_period):
    room_sharing = (form.get('room_sharing') or '').strip().lower()
    if room_sharing and room_sharing not in ROOM_SHARING_OPTIONS:
        raise ValueError('Choose either Single Room or Shared Room.')
    if property_type == 'Boarding House' and not room_sharing:
        room_sharing = 'single'

    upfront_raw = (form.get('upfront_months') or '1').strip()
    try:
        upfront_months = int(upfront_raw) if price_period == 'month' else 1
    except ValueError:
        raise ValueError('Choose a valid upfront months option.')
    if upfront_months < 1 or upfront_months > 24:
        raise ValueError('Upfront payment requirement must be between 1 and 24 months.')

    hourly_raw = (form.get('hourly_rate') or '').strip()
    hourly_rate = None
    if price_period != 'month' and hourly_raw:
        hourly_rate = parse_nonnegative_money(hourly_raw, 'Hourly rate')
        if hourly_rate <= 0:
            hourly_rate = None

    return {
        'room_sharing': room_sharing or None,
        'upfront_months': upfront_months,
        'hourly_rate': hourly_rate,
    }


def parse_checkin_fields(form, is_long_term=False):
    if is_long_term:
        checkin_time = form.get('checkin_time', '').strip()
        checkout_time = form.get('checkout_time', '').strip()
    else:
        checkin_time = form.get('checkin_time', '').strip() or '15:00'
        checkout_time = form.get('checkout_time', '').strip() or '10:00'
    self_checkin_method = form.get('self_checkin_method', '').strip()
    for label, value in (('Check-in', checkin_time), ('Check-out', checkout_time)):
        if is_long_term and not value:
            continue
        if not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', value):
            raise ValueError(f'{label} time must use 24-hour HH:MM format.')
    if self_checkin_method and self_checkin_method not in SELF_CHECKIN_OPTIONS:
        raise ValueError('Choose a valid check-in method.')
    return {
        'checkin_time': checkin_time,
        'checkout_time': checkout_time,
        'self_checkin_method': self_checkin_method or None,
    }


def add_months(start_date, months):
    month_index = start_date.month - 1 + months
    year = start_date.year + month_index // 12
    month = month_index % 12 + 1
    day = min(start_date.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def get_host_response_stats(db, owner_id):
    inquiries = db.execute(
        '''SELECT inquiry.id,
                  MIN((julianday(reply.created_at) - julianday(inquiry.created_at)) * 24)
                      AS response_hours
           FROM messages inquiry
           JOIN properties p ON p.id = inquiry.property_id AND p.owner_id = ?
           LEFT JOIN messages reply
             ON reply.parent_id = inquiry.id
            AND reply.sender_id = p.owner_id
            AND julianday(reply.created_at) >= julianday(inquiry.created_at)
           WHERE inquiry.receiver_id = p.owner_id
             AND inquiry.sender_id != p.owner_id
             AND inquiry.parent_id IS NULL
             AND julianday(inquiry.created_at) >= julianday('now', '-90 days')
           GROUP BY inquiry.id
           ORDER BY inquiry.created_at DESC''',
        (owner_id,),
    ).fetchall()
    if len(inquiries) < 3:
        return None

    durations = sorted(
        row['response_hours'] for row in inquiries
        if row['response_hours'] is not None
    )
    within_one_hour = sum(hours <= 1 for hours in durations)
    within_three_hours = sum(hours <= 3 for hours in durations)
    within_one_day = sum(hours <= 24 for hours in durations)
    response_rate = len(durations) / len(inquiries)
    median_hours = None
    if durations:
        middle = len(durations) // 2
        median_hours = (
            durations[middle] if len(durations) % 2
            else (durations[middle - 1] + durations[middle]) / 2
        )

    if within_one_hour / len(inquiries) >= 0.7:
        label = 'Usually replies within an hour'
    elif within_three_hours / len(inquiries) >= 0.7:
        label = 'Usually replies within a few hours'
    elif within_one_day / len(inquiries) >= 0.7:
        label = 'Usually replies within a day'
    elif response_rate >= 0.7 and median_hours is not None:
        label = f'Usually replies in about {max(1, round(median_hours))} hours'
    elif response_rate >= 0.4:
        label = 'Replies to some enquiries'
    else:
        label = 'Response times vary'

    return {
        'label': label,
        'inquiry_count': len(inquiries),
        'reply_rate_percent': round(response_rate * 100),
        'average_response_hours': (
            sum(durations) / len(durations) if durations else None
        ),
    }


def get_host_reliability_stats(db, owner_id):
    row = db.execute(
        '''SELECT
               SUM(CASE WHEN b.booking_status = 'confirmed'
                         AND b.check_out <= date('now') THEN 1 ELSE 0 END) AS completed_stays,
               SUM(CASE WHEN b.booking_status IN ('confirmed', 'declined')
                         THEN 1 ELSE 0 END) AS host_decisions,
               SUM(CASE WHEN b.booking_status = 'confirmed'
                         THEN 1 ELSE 0 END) AS host_confirmations
           FROM bookings b
           JOIN properties p ON p.id = b.property_id
           WHERE p.owner_id = ?''',
        (owner_id,),
    ).fetchone()
    completed_stays = row['completed_stays'] or 0
    decisions = row['host_decisions'] or 0
    return {
        'completed_stays': completed_stays,
        'confirmation_rate': (
            round((row['host_confirmations'] or 0) * 100 / decisions)
            if decisions >= 5 else None
        ),
    }


def booking_conflict(db, property_id, check_in, check_out, exclude_booking_id=None):
    params = [
        property_id, f'-{BOOKING_REQUEST_EXPIRY_HOURS} hours',
        check_out.isoformat(), check_in.isoformat(),
    ]
    exclude_sql = ''
    if exclude_booking_id is not None:
        exclude_sql = ' AND id != ?'
        params.append(exclude_booking_id)

    conflict = db.execute(
        '''SELECT id FROM bookings
           WHERE property_id = ?
             AND booking_status IN ('pending', 'confirmed')
             AND (booking_status = 'confirmed'
                  OR julianday(created_at) > julianday('now', ?))
             AND check_in < ? AND check_out > ?''' + exclude_sql + ' LIMIT 1',
        params,
    ).fetchone()
    if conflict:
        return 'Those dates overlap an existing booking request or confirmed stay.'

    imported_conflict = db.execute(
        '''SELECT cie.id FROM calendar_import_events cie
           JOIN calendar_imports ci ON ci.id = cie.import_id
           WHERE ci.property_id = ? AND cie.start_date < ? AND cie.end_date > ?
           LIMIT 1''',
        (property_id, check_out.isoformat(), check_in.isoformat()),
    ).fetchone()
    if imported_conflict:
        return 'These dates are blocked by a stay on a connected external calendar.'

    blocked = db.execute(
        '''SELECT date FROM availability
           WHERE property_id = ? AND status = 'blocked'
             AND date >= ? AND date < ? LIMIT 1''',
        (property_id, check_in.isoformat(), check_out.isoformat()),
    ).fetchone()
    if blocked:
        return f'The property is unavailable on {blocked["date"]}.'
    return None


def seasonal_rule_for_date(db, property_id, selected_date):
    return db.execute(
        '''SELECT price, minimum_stay FROM seasonal_pricing
           WHERE property_id = ? AND start_date <= ? AND end_date > ?
           ORDER BY start_date DESC LIMIT 1''',
        (property_id, selected_date.isoformat(), selected_date.isoformat()),
    ).fetchone()


def quote_property_stay(db, property_row, check_in, duration, duration_unit_override=None):
    default_unit = 'month' if property_row['price_period'] == 'month' else 'night'
    if duration_unit_override == 'hour' and supports_hourly_booking(property_row):
        duration_unit = 'hour'
    else:
        duration_unit = default_unit

    if duration_unit == 'hour':
        if duration < MIN_HOURLY_STAY_HOURS or duration > MAX_HOURLY_STAY_HOURS:
            raise ValueError(
                f'Hourly stays require a minimum of {MIN_HOURLY_STAY_HOURS} hours '
                f'(up to {MAX_HOURLY_STAY_HOURS} hours).'
            )
        check_out = check_in + timedelta(days=1)
        hourly_rate = get_effective_hourly_rate(property_row)
        base_amount = round(hourly_rate * duration, 2)
        cleaning_fee = float(property_row['cleaning_fee'] or 0)
        return {
            'check_out': check_out,
            'duration_unit': 'hour',
            'unit_price': hourly_rate,
            'base_amount': base_amount,
            'service_fee': BOOKING_SERVICE_FEE,
            'cleaning_fee': cleaning_fee,
            'refundable_deposit': float(property_row['refundable_deposit'] or 0),
            'total_price': round(base_amount + BOOKING_SERVICE_FEE + cleaning_fee, 2),
            'minimum_stay': MIN_HOURLY_STAY_HOURS,
        }

    check_out = (
        add_months(check_in, duration) if duration_unit == 'month'
        else check_in + timedelta(days=duration)
    )
    start_rule = seasonal_rule_for_date(db, property_row['id'], check_in)
    minimum_stay = start_rule['minimum_stay'] if start_rule else 1
    if duration_unit == 'month':
        upfront_min = get_upfront_months(property_row)
        if upfront_min > minimum_stay:
            minimum_stay = upfront_min
    if duration < minimum_stay:
        if duration_unit == 'month' and minimum_stay == get_upfront_months(property_row) and minimum_stay > 1:
            raise ValueError(f'This property requires at least {minimum_stay} months paid upfront.')
        raise ValueError(f'This listing requires a minimum stay of {minimum_stay} {duration_unit}(s) for those dates.')

    base_amount = 0.0
    current = check_in
    while current < check_out:
        rule = seasonal_rule_for_date(db, property_row['id'], current)
        unit_price = (
            float(rule['price']) if rule and rule['price'] is not None
            else float(property_row['price_per_night'])
        )
        base_amount += unit_price
        current = add_months(current, 1) if duration_unit == 'month' else current + timedelta(days=1)
    base_amount = round(base_amount, 2)
    cleaning_fee = float(property_row['cleaning_fee'] or 0)
    return {
        'check_out': check_out,
        'duration_unit': duration_unit,
        'unit_price': float(property_row['price_per_night']),
        'base_amount': base_amount,
        'service_fee': BOOKING_SERVICE_FEE,
        'cleaning_fee': cleaning_fee,
        'refundable_deposit': float(property_row['refundable_deposit'] or 0),
        'total_price': round(base_amount + BOOKING_SERVICE_FEE + cleaning_fee, 2),
        'minimum_stay': minimum_stay,
    }


def refresh_payout_ledger(db, owner_id):
    db.execute(
        '''INSERT OR IGNORE INTO payout_ledger (booking_id, owner_id, amount, status)
           SELECT b.id, p.owner_id,
                  CASE WHEN b.base_amount + b.cleaning_fee > 0
                       THEN b.base_amount + b.cleaning_fee ELSE 0 END,
                  'pending'
           FROM bookings b
           JOIN properties p ON p.id = b.property_id
           WHERE p.owner_id = ? AND b.booking_status = 'confirmed'
             AND b.payment_status = 'paid'
             AND b.refund_status NOT IN ('processing', 'refunded')''',
        (owner_id,),
    )
    db.execute(
        '''UPDATE payout_ledger SET amount = 0, status = 'on_hold'
           WHERE owner_id = ? AND status = 'pending'
             AND booking_id IN (
                 SELECT id FROM bookings WHERE refund_status IN ('processing', 'refunded')
             )''',
        (owner_id,),
    )


def expire_pending_booking_requests(db, force=False):
    global _last_booking_expiry_sweep
    with _booking_expiry_sweep_lock:
        if not force and time.monotonic() - _last_booking_expiry_sweep < 30:
            return
        try:
            db.execute('BEGIN IMMEDIATE')
            stale_bookings = db.execute(
                '''SELECT id, user_id, tx_ref, payment_status FROM bookings
                   WHERE booking_status = 'pending'
                     AND julianday(created_at) <= julianday('now', ?)''',
                (f'-{BOOKING_REQUEST_EXPIRY_HOURS} hours',),
            ).fetchall()
            for booking in stale_bookings:
                updated = db.execute(
                    '''UPDATE bookings SET booking_status = 'expired',
                           refund_status = CASE
                               WHEN payment_status = 'paid'
                                AND COALESCE(refund_status, 'none') IN ('none', 'rejected') THEN 'requested'
                               ELSE refund_status
                           END
                       WHERE id = ? AND booking_status = 'pending' ''',
                    (booking['id'],),
                )
                if updated.rowcount and booking['user_id']:
                    create_notification(
                        db,
                        booking['user_id'],
                        f'Your booking request {booking["tx_ref"] or "#" + str(booking["id"])} expired because the host did not respond in time. The dates are available again.'
                        + (' A refund has been requested for your verified payment.'
                           if booking['payment_status'] == 'paid' else ''),
                        url_for('booking_receipt', booking_id=booking['id']),
                    )
            db.commit()
            _last_booking_expiry_sweep = time.monotonic()
        except DB_ERRORS:
            db.rollback()
            app.logger.exception('Could not expire stale booking requests')


def flutterwave_api_request(method, path, payload=None):
    if not FLUTTERWAVE_SECRET_KEY:
        raise RuntimeError('Mobile-money checkout is not configured. Add FLUTTERWAVE_SECRET_KEY to the server environment.')
    body = json.dumps(payload).encode('utf-8') if payload is not None else None
    api_request = urllib.request.Request(
        'https://api.flutterwave.com/v3/' + path.lstrip('/'),
        data=body,
        headers={
            'Authorization': f'Bearer {FLUTTERWAVE_SECRET_KEY}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(api_request, timeout=15) as response:
            result = json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as error:
        raise RuntimeError(f'Flutterwave returned HTTP {error.code}.') from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise RuntimeError('Could not connect to Flutterwave. Please try again.') from error
    except json.JSONDecodeError as error:
        raise RuntimeError('Flutterwave returned an unreadable response.') from error
    is_refund_lookup = method == 'GET' and path.startswith('refunds/')
    if not isinstance(result, dict) or (
            result.get('status') != 'success'
            and not (is_refund_lookup and result.get('status'))):
        raise RuntimeError('Flutterwave did not accept the request.')
    return result


def verify_flutterwave_transaction(transaction_id, expected_tx_ref, expected_amount):
    if not str(transaction_id).isdigit():
        raise ValueError('Invalid payment transaction reference.')
    result = flutterwave_api_request('GET', f'transactions/{transaction_id}/verify')
    transaction = result.get('data') or {}
    try:
        amount = round(float(transaction.get('amount')), 2)
    except (TypeError, ValueError):
        raise ValueError('Flutterwave returned an invalid transaction amount.')
    if (transaction.get('status') != 'successful'
            or str(transaction.get('id')) != str(transaction_id)
            or transaction.get('currency') != 'ZMW'
            or amount != round(float(expected_amount), 2)
            or transaction.get('tx_ref') != expected_tx_ref):
        raise ValueError('Payment could not be verified against this booking and amount.')
    return transaction


def record_flutterwave_payment(db, tx_ref, transaction_id):
    attempt = db.execute(
        '''SELECT pa.id AS attempt_id, pa.booking_id, pa.tx_ref,
                  b.user_id, b.total_price
           FROM payment_attempts pa
           JOIN bookings b ON b.id = pa.booking_id
           WHERE pa.tx_ref = ? AND pa.provider = 'flutterwave' ''',
        (tx_ref,),
    ).fetchone()
    if not attempt:
        raise ValueError('Payment reference was not found.')
    transaction = verify_flutterwave_transaction(
        transaction_id, attempt['tx_ref'], attempt['total_price']
    )
    payment_reference = str(transaction['id'])
    db.execute('BEGIN IMMEDIATE')
    current = db.execute(
        '''SELECT payment_status, payment_method, payment_reference, booking_status
           FROM bookings WHERE id = ?''',
        (attempt['booking_id'],),
    ).fetchone()
    if (current['payment_status'] == 'paid'
            and current['payment_method'] == 'Flutterwave Mobile Money'
            and current['payment_reference'] != payment_reference):
        db.rollback()
        raise ValueError('A different Flutterwave transaction is already recorded for this booking.')
    if current['payment_status'] != 'paid':
        refund_status = (
            'requested' if current['booking_status'] in ('declined', 'cancelled', 'expired')
            else 'none'
        )
        updated = db.execute(
            '''UPDATE bookings SET payment_status = 'paid',
                   payment_method = 'Flutterwave Mobile Money',
                   payment_reference = ?, refund_status = ?
               WHERE id = ? AND payment_status != 'paid' ''',
            (payment_reference, refund_status, attempt['booking_id']),
        )
        if updated.rowcount != 1:
            db.rollback()
            raise RuntimeError('Booking payment status changed during verification.')
        if attempt['user_id']:
            create_notification(
                db, attempt['user_id'],
                f'Payment verified for booking #{attempt["booking_id"]}.',
                url_for('booking_receipt', booking_id=attempt['booking_id']),
            )
    db.execute(
        '''UPDATE payment_attempts
           SET status = 'paid', provider_transaction_id = ?,
               provider_reference = ?, updated_at = CURRENT_TIMESTAMP
           WHERE id = ?''',
        (payment_reference, str(transaction.get('flw_ref') or ''), attempt['attempt_id']),
    )
    db.commit()
    return attempt['booking_id']


def flutterwave_checkout_enabled():
    public_url = urllib.parse.urlparse(PUBLIC_BASE_URL)
    return bool(FLUTTERWAVE_SECRET_KEY and public_url.scheme == 'https'
                and public_url.hostname and not public_url.username and not public_url.password
                and public_url.path in ('', '/') and not public_url.query and not public_url.fragment)


def saved_search_matches_property(saved, property_row, include_price=True):
    searchable_text = ' '.join(
        str(property_row[key] or '')
        for key in ('title', 'description', 'compound', 'location_details', 'property_type')
    ).casefold()
    if (saved['compound'] and saved['compound'] != 'All'
            and saved['compound'].casefold() != str(property_row['compound']).casefold()):
        return False
    if (saved['property_type'] and saved['property_type'] != 'All'
            and saved['property_type'].casefold() != str(property_row['property_type']).casefold()):
        return False
    if saved['power_backup'] and saved['power_backup'] != property_row['power_backup']:
        return False
    if saved['water_supply'] and saved['water_supply'] != property_row['water_supply']:
        return False
    if saved['near_lat'] is not None or saved['near_lon'] is not None:
        if (saved['near_lat'] is None or saved['near_lon'] is None
                or saved['near_radius_km'] is None
                or property_row['latitude'] is None or property_row['longitude'] is None):
            return False
        if distance_km(
                saved['near_lat'], saved['near_lon'],
                property_row['latitude'], property_row['longitude']
        ) > saved['near_radius_km']:
            return False
    if saved['search_query'] and not all(
        word.casefold() in searchable_text for word in saved['search_query'].split()
    ):
        return False
    if include_price:
        price = float(property_row['price_per_night'])
        if saved['min_price'] is not None and price < saved['min_price']:
            return False
        if saved['max_price'] is not None and price > saved['max_price']:
            return False
    return True


def distance_km(latitude_a, longitude_a, latitude_b, longitude_b):
    if None in (latitude_a, longitude_a, latitude_b, longitude_b):
        return None
    latitude_a, longitude_a, latitude_b, longitude_b = map(
        math.radians, map(float, (latitude_a, longitude_a, latitude_b, longitude_b))
    )
    latitude_delta = latitude_b - latitude_a
    longitude_delta = longitude_b - longitude_a
    haversine = (
        math.sin(latitude_delta / 2) ** 2
        + math.cos(latitude_a) * math.cos(latitude_b)
        * math.sin(longitude_delta / 2) ** 2
    )
    return 6371 * 2 * math.asin(math.sqrt(min(1, haversine)))


def notify_matching_searches(db, property_row, event='new', previous_price=None):
    searches = db.execute(
        'SELECT * FROM saved_searches WHERE user_id != ?',
        (property_row['owner_id'],),
    ).fetchall()
    for saved in searches:
        if not saved_search_matches_property(
                saved, property_row, include_price=(event != 'price')):
            continue
        if event == 'price':
            current_price = float(property_row['price_per_night'])
            if previous_price is None or current_price == float(previous_price):
                continue
            old_price_matches = (
                (saved['min_price'] is None or float(previous_price) >= saved['min_price'])
                and (saved['max_price'] is None or float(previous_price) <= saved['max_price'])
            )
            if not old_price_matches and not saved_search_matches_property(saved, property_row):
                continue
            message = (
                f'{property_row["title"]} changed price from ZMW {float(previous_price):,.0f} '
                f'to ZMW {current_price:,.0f} and matches your saved search.'
            )
        elif event == 'available':
            message = f'A saved-search listing is available again: {property_row["title"]}.'
        else:
            message = f'A new listing matches your saved search: {property_row["title"]}.'
        db.execute(
            '''INSERT INTO notifications (user_id, message, link)
               VALUES (?, ?, ?)''',
            (saved['user_id'], message,
             url_for('property_details', property_id=property_row['id'])),
        )

# --- Database setup ---
def get_db():
    if 'db' not in g.__dict__:
        if DATABASE_URL:
            g.db = connect_postgres(DATABASE_URL)
        else:
            if not os.path.exists(DATABASE):
                init_db()
            conn = sqlite3.connect(DATABASE, timeout=30)
            conn.row_factory = sqlite3.Row
            conn.execute('PRAGMA busy_timeout = 30000')
            conn.execute('PRAGMA foreign_keys = ON')
            conn.create_function('distance_km', 4, distance_km)
            g.db = conn
    return g.db

@app.teardown_appcontext
def close_db(exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    conn = sqlite3.connect(DATABASE, timeout=30)
    conn.execute('PRAGMA busy_timeout = 30000')
    conn.execute('PRAGMA foreign_keys = ON')
    try:
        with open('schema.sql', 'r', encoding='utf-8') as f:
            conn.executescript(f.read())

        # Additional columns/features used by the app but not always present in older DBs.
        def column_exists(table_name, column_name):
            rows = conn.execute(f'PRAGMA table_info({table_name})').fetchall()
            return any(row[1] == column_name for row in rows)

        if not column_exists('users', 'is_admin'):
            conn.execute('ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0')
        if not column_exists('users', 'profile_pic'):
            conn.execute('ALTER TABLE users ADD COLUMN profile_pic TEXT')
        if not column_exists('users', 'password_reset_token'):
            conn.execute('ALTER TABLE users ADD COLUMN password_reset_token TEXT')
        if not column_exists('users', 'password_reset_expires'):
            conn.execute('ALTER TABLE users ADD COLUMN password_reset_expires REAL')
        if not column_exists('users', 'host_verification_status'):
            conn.execute("ALTER TABLE users ADD COLUMN host_verification_status TEXT DEFAULT 'unverified'")
        if not column_exists('users', 'host_verification_note'):
            conn.execute('ALTER TABLE users ADD COLUMN host_verification_note TEXT')

        if not column_exists('properties', 'bedrooms'):
            conn.execute('ALTER TABLE properties ADD COLUMN bedrooms INTEGER DEFAULT 1')
        if not column_exists('properties', 'bathrooms'):
            conn.execute('ALTER TABLE properties ADD COLUMN bathrooms INTEGER DEFAULT 1')
        if not column_exists('properties', 'listing_category'):
            conn.execute("ALTER TABLE properties ADD COLUMN listing_category TEXT DEFAULT 'rental'")
        if not column_exists('properties', 'availability_status'):
            conn.execute("ALTER TABLE properties ADD COLUMN availability_status TEXT DEFAULT 'available'")
        if not column_exists('properties', 'location_details'):
            conn.execute('ALTER TABLE properties ADD COLUMN location_details TEXT')
        if not column_exists('properties', 'agent_name'):
            conn.execute('ALTER TABLE properties ADD COLUMN agent_name TEXT')
        if not column_exists('properties', 'agent_phone'):
            conn.execute('ALTER TABLE properties ADD COLUMN agent_phone TEXT')
        if not column_exists('properties', 'is_featured'):
            conn.execute('ALTER TABLE properties ADD COLUMN is_featured BOOLEAN DEFAULT 0')
        if not column_exists('properties', 'view_count'):
            conn.execute('ALTER TABLE properties ADD COLUMN view_count INTEGER DEFAULT 0')
        if not column_exists('properties', 'cancellation_policy'):
            conn.execute("ALTER TABLE properties ADD COLUMN cancellation_policy TEXT DEFAULT 'moderate'")
        if not column_exists('properties', 'house_rules'):
            conn.execute('ALTER TABLE properties ADD COLUMN house_rules TEXT')
        if not column_exists('properties', 'last_confirmed_at'):
            conn.execute('ALTER TABLE properties ADD COLUMN last_confirmed_at TIMESTAMP')
        if not column_exists('properties', 'latitude'):
            conn.execute('ALTER TABLE properties ADD COLUMN latitude REAL')
        if not column_exists('properties', 'longitude'):
            conn.execute('ALTER TABLE properties ADD COLUMN longitude REAL')
        for column_name, ddl in {
            'cleaning_fee': 'REAL NOT NULL DEFAULT 0',
            'refundable_deposit': 'REAL NOT NULL DEFAULT 0',
            'utilities_included': 'BOOLEAN NOT NULL DEFAULT 0',
            'power_backup': 'TEXT',
            'water_supply': 'TEXT',
            'internet_availability': 'TEXT',
            'internet_speed_mbps': 'INTEGER',
            'room_sharing': 'TEXT',
            'upfront_months': 'INTEGER NOT NULL DEFAULT 1',
            'hourly_rate': 'REAL',
            'arrival_instructions': 'TEXT',
            'arrival_directions': 'TEXT',
            'nearby_essentials': 'TEXT',
            'emergency_contact_name': 'TEXT',
            'emergency_contact_phone': 'TEXT',
            'main_photo_category': "TEXT DEFAULT 'other'",
        }.items():
            if not column_exists('properties', column_name):
                conn.execute(f'ALTER TABLE properties ADD COLUMN {column_name} {ddl}')

        if not column_exists('bookings', 'booking_status'):
            conn.execute("ALTER TABLE bookings ADD COLUMN booking_status TEXT DEFAULT 'pending'")
        if not column_exists('bookings', 'payment_method'):
            conn.execute('ALTER TABLE bookings ADD COLUMN payment_method TEXT')
        if not column_exists('bookings', 'duration'):
            conn.execute('ALTER TABLE bookings ADD COLUMN duration INTEGER')
        if not column_exists('bookings', 'duration_unit'):
            conn.execute("ALTER TABLE bookings ADD COLUMN duration_unit TEXT DEFAULT 'night'")
        if not column_exists('bookings', 'refund_status'):
            conn.execute("ALTER TABLE bookings ADD COLUMN refund_status TEXT DEFAULT 'none'")
        if not column_exists('bookings', 'payment_reference'):
            conn.execute('ALTER TABLE bookings ADD COLUMN payment_reference TEXT')
        for column_name in ('base_amount', 'service_fee', 'cleaning_fee', 'refundable_deposit'):
            if not column_exists('bookings', column_name):
                conn.execute(f'ALTER TABLE bookings ADD COLUMN {column_name} REAL NOT NULL DEFAULT 0')
        if not column_exists('bookings', 'refund_reference'):
            conn.execute('ALTER TABLE bookings ADD COLUMN refund_reference TEXT')

        for column_name in ('cleanliness_rating', 'accuracy_rating', 'communication_rating', 'location_rating'):
            if not column_exists('reviews', column_name):
                conn.execute(f'ALTER TABLE reviews ADD COLUMN {column_name} INTEGER')

        ensure_feature_schema(conn)
        if not column_exists('property_images', 'category'):
            conn.execute("ALTER TABLE property_images ADD COLUMN category TEXT NOT NULL DEFAULT 'other'")

        if not column_exists('messages', 'is_read'):
            conn.execute('ALTER TABLE messages ADD COLUMN is_read BOOLEAN DEFAULT 0')
        if not column_exists('messages', 'parent_id'):
            conn.execute('ALTER TABLE messages ADD COLUMN parent_id INTEGER REFERENCES messages(id)')

        conn.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                message TEXT NOT NULL,
                link TEXT,
                is_read BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS saved_searches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                search_query TEXT,
                compound TEXT,
                min_price REAL,
                max_price REAL,
                property_type TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS property_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                property_id INTEGER NOT NULL,
                reporter_id INTEGER NOT NULL,
                reason TEXT NOT NULL,
                details TEXT,
                status TEXT NOT NULL DEFAULT 'open',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (property_id) REFERENCES properties (id),
                FOREIGN KEY (reporter_id) REFERENCES users (id)
            )
        ''')
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS trip_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                share_token TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL DEFAULT 'My Lusaka shortlist',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS trip_plan_items (
                trip_plan_id INTEGER NOT NULL,
                property_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (trip_plan_id, property_id),
                FOREIGN KEY (trip_plan_id) REFERENCES trip_plans (id) ON DELETE CASCADE,
                FOREIGN KEY (property_id) REFERENCES properties (id) ON DELETE CASCADE
            );
        ''')
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS payment_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                booking_id INTEGER NOT NULL,
                tx_ref TEXT NOT NULL UNIQUE,
                provider TEXT NOT NULL DEFAULT 'flutterwave',
                status TEXT NOT NULL DEFAULT 'pending',
                checkout_url TEXT,
                provider_transaction_id TEXT,
                provider_reference TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (booking_id) REFERENCES bookings (id)
            );
            CREATE INDEX IF NOT EXISTS idx_payment_attempt_booking
                ON payment_attempts(booking_id, created_at DESC);
            CREATE TABLE IF NOT EXISTS support_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reporter_id INTEGER NOT NULL,
                booking_id INTEGER,
                category TEXT NOT NULL,
                details TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                admin_note TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (reporter_id) REFERENCES users (id),
                FOREIGN KEY (booking_id) REFERENCES bookings (id)
            );
        ''')
        conn.execute('''CREATE UNIQUE INDEX IF NOT EXISTS idx_bookings_payment_reference
                        ON bookings(payment_reference)
                        WHERE payment_reference IS NOT NULL AND payment_reference != '' ''')

        conn.commit()
    finally:
        conn.close()


def ensure_feature_schema(conn):
    if not any(row[1] == 'payment_claim_reference' for row in conn.execute('PRAGMA table_info(bookings)')):
        conn.execute('ALTER TABLE bookings ADD COLUMN payment_claim_reference TEXT')
    if not any(row[1] == 'payment_claim_submitted_at' for row in conn.execute('PRAGMA table_info(bookings)')):
        conn.execute('ALTER TABLE bookings ADD COLUMN payment_claim_submitted_at TIMESTAMP')

    for column_name, ddl in {
        'email_verified_at': 'TIMESTAMP',
        'email_verification_token': 'TEXT',
        'email_verification_expires': 'REAL',
        'email_verification_code_hash': 'TEXT',
        'email_verification_code_expires': 'REAL',
        'email_verification_sent_at': 'REAL',
        'email_verification_attempts': 'INTEGER NOT NULL DEFAULT 0',
        'phone_verified_at': 'TIMESTAMP',
        'phone_verification_token': 'TEXT',
        'phone_verification_expires': 'REAL',
        'phone_verification_sent_at': 'REAL',
        'phone_verification_attempts': 'INTEGER NOT NULL DEFAULT 0',
        'email_verification_token_hash': 'TEXT',
        'email_delivery_status': "TEXT DEFAULT 'unknown'",
        'email_delivery_last_event': 'TEXT',
        'email_bounced_at': 'REAL',
        'password_reset_token_hash': 'TEXT',
        'session_version': 'INTEGER NOT NULL DEFAULT 1',
        'totp_secret': 'TEXT',
        'totp_enabled': 'BOOLEAN NOT NULL DEFAULT 0',
    }.items():
        if not any(row[1] == column_name for row in conn.execute('PRAGMA table_info(users)')):
            conn.execute(f'ALTER TABLE users ADD COLUMN {column_name} {ddl}')

    # Migrate any tokens created by the older implementation into hashed storage,
    # then clear the legacy plaintext columns so they cannot leak from the DB.
    legacy_tokens = conn.execute(
        '''SELECT id, email_verification_token, email_verification_token_hash,
                  password_reset_token, password_reset_token_hash FROM users'''
    ).fetchall()
    for row in legacy_tokens:
        if row[1] and not row[2]:
            conn.execute(
                'UPDATE users SET email_verification_token_hash = ? WHERE id = ?',
                (token_digest(row[1]), row[0]),
            )
        if row[3] and not row[4]:
            conn.execute(
                'UPDATE users SET password_reset_token_hash = ? WHERE id = ?',
                (token_digest(row[3]), row[0]),
            )
    conn.execute('UPDATE users SET email_verification_token = NULL, password_reset_token = NULL')
    for column_name, ddl in {
        'checkin_time': "TEXT NOT NULL DEFAULT '15:00'",
        'checkout_time': "TEXT NOT NULL DEFAULT '10:00'",
        'self_checkin_method': 'TEXT',
    }.items():
        if not any(row[1] == column_name for row in conn.execute('PRAGMA table_info(properties)')):
            conn.execute(f'ALTER TABLE properties ADD COLUMN {column_name} {ddl}')

    saved_search_columns = {
        row[1] for row in conn.execute('PRAGMA table_info(saved_searches)')
    }
    for column_name in ('power_backup', 'water_supply', 'near_lat', 'near_lon', 'near_radius_km'):
        if column_name not in saved_search_columns:
            column_type = 'REAL' if column_name.startswith('near_') else 'TEXT'
            conn.execute(f'ALTER TABLE saved_searches ADD COLUMN {column_name} {column_type}')

    conn.executescript('''
        CREATE TABLE IF NOT EXISTS review_photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            review_id INTEGER NOT NULL,
            image_url TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (review_id) REFERENCES reviews(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS calendar_feeds (
            property_id INTEGER PRIMARY KEY,
            owner_id INTEGER NOT NULL,
            token_hash TEXT NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE,
            FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS calendar_imports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            property_id INTEGER NOT NULL,
            source_name TEXT NOT NULL,
            imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(property_id, source_name),
            FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS calendar_import_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            import_id INTEGER NOT NULL,
            event_uid TEXT NOT NULL,
            start_date DATE NOT NULL,
            end_date DATE NOT NULL,
            FOREIGN KEY (import_id) REFERENCES calendar_imports(id) ON DELETE CASCADE,
            UNIQUE(import_id, event_uid)
        );
        CREATE INDEX IF NOT EXISTS idx_import_events_dates
            ON calendar_import_events(start_date, end_date);
        CREATE TABLE IF NOT EXISTS seasonal_pricing (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            property_id INTEGER NOT NULL,
            start_date DATE NOT NULL,
            end_date DATE NOT NULL,
            price REAL,
            minimum_stay INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CHECK (end_date > start_date),
            CHECK (price IS NULL OR price >= 0),
            CHECK (minimum_stay BETWEEN 1 AND 365),
            FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_seasonal_pricing_dates
            ON seasonal_pricing(property_id, start_date, end_date);
        CREATE TABLE IF NOT EXISTS payout_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_id INTEGER NOT NULL UNIQUE,
            owner_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            reference TEXT,
            paid_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (booking_id) REFERENCES bookings(id) ON DELETE CASCADE,
            FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS email_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider TEXT NOT NULL,
            provider_message_id TEXT,
            recipient TEXT NOT NULL,
            subject TEXT NOT NULL,
            template_key TEXT,
            status TEXT NOT NULL DEFAULT 'accepted',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            sent_at REAL,
            delivered_at REAL,
            delayed_at REAL,
            bounced_at REAL,
            failed_at REAL,
            complained_at REAL,
            last_event_at REAL,
            failure_reason TEXT,
            UNIQUE(provider, provider_message_id)
        );
        CREATE TABLE IF NOT EXISTS email_webhook_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider TEXT NOT NULL,
            event_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            payload TEXT NOT NULL,
            received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(provider, event_id)
        );
        CREATE TABLE IF NOT EXISTS email_rate_limits (
            action TEXT NOT NULL,
            rate_key TEXT NOT NULL,
            window_started REAL NOT NULL,
            request_count INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY(action, rate_key)
        );
        CREATE TABLE IF NOT EXISTS admin_audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER,
            admin_email TEXT,
            action TEXT NOT NULL,
            target_type TEXT,
            target_id TEXT,
            details TEXT,
            ip_address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (admin_id) REFERENCES users (id) ON DELETE SET NULL
        );
        CREATE INDEX IF NOT EXISTS idx_admin_audit_logs_created_at
            ON admin_audit_logs(created_at DESC);
    ''')


def ensure_db_schema():
    if not os.path.exists(DATABASE):
        init_db()
        return

    conn = sqlite3.connect(DATABASE, timeout=30)
    conn.execute('PRAGMA busy_timeout = 30000')
    try:
        conn.execute('PRAGMA foreign_keys = ON')
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if 'properties' in tables:
            properties_cols = {row[1] for row in conn.execute('PRAGMA table_info(properties)').fetchall()}
            for column_name, ddl in {
                'bedrooms': 'INTEGER DEFAULT 1',
                'bathrooms': 'INTEGER DEFAULT 1',
                'listing_category': "TEXT DEFAULT 'rental'",
                'availability_status': "TEXT DEFAULT 'available'",
                'location_details': 'TEXT',
                'agent_name': 'TEXT',
                'agent_phone': 'TEXT',
                'is_featured': 'BOOLEAN DEFAULT 0',
                'view_count': 'INTEGER DEFAULT 0',
                'cancellation_policy': "TEXT DEFAULT 'moderate'",
                'house_rules': 'TEXT',
                'last_confirmed_at': 'TIMESTAMP',
                'latitude': 'REAL',
                'longitude': 'REAL',
                'cleaning_fee': 'REAL NOT NULL DEFAULT 0',
                'refundable_deposit': 'REAL NOT NULL DEFAULT 0',
                'utilities_included': 'BOOLEAN NOT NULL DEFAULT 0',
                'power_backup': 'TEXT',
                'water_supply': 'TEXT',
                'internet_availability': 'TEXT',
                'internet_speed_mbps': 'INTEGER',
                'room_sharing': 'TEXT',
                'upfront_months': 'INTEGER NOT NULL DEFAULT 1',
                'hourly_rate': 'REAL',
                'arrival_instructions': 'TEXT',
                'arrival_directions': 'TEXT',
                'nearby_essentials': 'TEXT',
                'emergency_contact_name': 'TEXT',
                'emergency_contact_phone': 'TEXT',
                'main_photo_category': "TEXT DEFAULT 'other'",
            }.items():
                if column_name not in properties_cols:
                    conn.execute(f'ALTER TABLE properties ADD COLUMN {column_name} {ddl}')

        if 'bookings' in tables:
            bookings_cols = {row[1] for row in conn.execute('PRAGMA table_info(bookings)').fetchall()}
            for column_name, ddl in {
                'booking_status': "TEXT DEFAULT 'pending'",
                'payment_method': 'TEXT',
                'duration': 'INTEGER',
                'duration_unit': "TEXT DEFAULT 'night'",
                'refund_status': "TEXT DEFAULT 'none'",
                'payment_reference': 'TEXT',
                'refund_reference': 'TEXT',
                'base_amount': 'REAL NOT NULL DEFAULT 0',
                'service_fee': 'REAL NOT NULL DEFAULT 0',
                'cleaning_fee': 'REAL NOT NULL DEFAULT 0',
                'refundable_deposit': 'REAL NOT NULL DEFAULT 0',
            }.items():
                if column_name not in bookings_cols:
                    conn.execute(f'ALTER TABLE bookings ADD COLUMN {column_name} {ddl}')

        if 'property_images' in tables:
            image_cols = {row[1] for row in conn.execute('PRAGMA table_info(property_images)').fetchall()}
            if 'category' not in image_cols:
                conn.execute("ALTER TABLE property_images ADD COLUMN category TEXT NOT NULL DEFAULT 'other'")

        if 'reviews' in tables:
            review_cols = {row[1] for row in conn.execute('PRAGMA table_info(reviews)').fetchall()}
            for column_name in ('cleanliness_rating', 'accuracy_rating', 'communication_rating', 'location_rating'):
                if column_name not in review_cols:
                    conn.execute(f'ALTER TABLE reviews ADD COLUMN {column_name} INTEGER')

        if 'users' in tables:
            users_cols = {row[1] for row in conn.execute('PRAGMA table_info(users)').fetchall()}
            for column_name, ddl in {
                'is_admin': 'BOOLEAN DEFAULT 0',
                'profile_pic': 'TEXT',
                'password_reset_token': 'TEXT',
                'password_reset_expires': 'REAL',
                'host_verification_status': "TEXT DEFAULT 'unverified'",
                'host_verification_note': 'TEXT',
            }.items():
                if column_name not in users_cols:
                    conn.execute(f'ALTER TABLE users ADD COLUMN {column_name} {ddl}')

        if 'messages' in tables:
            messages_cols = {row[1] for row in conn.execute('PRAGMA table_info(messages)').fetchall()}
            if 'is_read' not in messages_cols:
                conn.execute('ALTER TABLE messages ADD COLUMN is_read BOOLEAN DEFAULT 0')
            if 'parent_id' not in messages_cols:
                conn.execute('ALTER TABLE messages ADD COLUMN parent_id INTEGER REFERENCES messages(id)')

        if 'notifications' not in tables:
            conn.execute('''
                CREATE TABLE notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    message TEXT NOT NULL,
                    link TEXT,
                    is_read BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')

        conn.execute('''
            CREATE TABLE IF NOT EXISTS saved_searches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                search_query TEXT,
                compound TEXT,
                min_price REAL,
                max_price REAL,
                property_type TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS property_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                property_id INTEGER NOT NULL,
                reporter_id INTEGER NOT NULL,
                reason TEXT NOT NULL,
                details TEXT,
                status TEXT NOT NULL DEFAULT 'open',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (property_id) REFERENCES properties (id),
                FOREIGN KEY (reporter_id) REFERENCES users (id)
            )
        ''')
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS trip_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                share_token TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL DEFAULT 'My Lusaka shortlist',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS trip_plan_items (
                trip_plan_id INTEGER NOT NULL,
                property_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (trip_plan_id, property_id),
                FOREIGN KEY (trip_plan_id) REFERENCES trip_plans (id) ON DELETE CASCADE,
                FOREIGN KEY (property_id) REFERENCES properties (id) ON DELETE CASCADE
            );
        ''')
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS payment_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                booking_id INTEGER NOT NULL,
                tx_ref TEXT NOT NULL UNIQUE,
                provider TEXT NOT NULL DEFAULT 'flutterwave',
                status TEXT NOT NULL DEFAULT 'pending',
                checkout_url TEXT,
                provider_transaction_id TEXT,
                provider_reference TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (booking_id) REFERENCES bookings (id)
            );
            CREATE INDEX IF NOT EXISTS idx_payment_attempt_booking
                ON payment_attempts(booking_id, created_at DESC);
            CREATE TABLE IF NOT EXISTS support_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reporter_id INTEGER NOT NULL,
                booking_id INTEGER,
                category TEXT NOT NULL,
                details TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                admin_note TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (reporter_id) REFERENCES users (id),
                FOREIGN KEY (booking_id) REFERENCES bookings (id)
            );
        ''')
        ensure_feature_schema(conn)
        conn.execute('''CREATE UNIQUE INDEX IF NOT EXISTS idx_bookings_payment_reference
                        ON bookings(payment_reference)
                        WHERE payment_reference IS NOT NULL AND payment_reference != '' ''')

        conn.commit()
    finally:
        conn.close()

# Ensure newer listing/search schema fields exist when app starts
if not DATABASE_URL:
    ensure_db_schema()

# --- Auth Decorators ---
def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('login'))
        return view(**kwargs)
    return wrapped_view


def tenant_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('login'))
        if g.user['role'] != 'tenant':
            message = (
                'This section is for Tenant accounts only. '
                'To rent or book a place, please log out and sign in or register with a separate Tenant account.'
            )
            if request.is_json or request.headers.get('X-CSRF-Token'):
                return jsonify({'error': message}), 403
            flash(message, 'info')
            if g.user['role'] == 'owner':
                return redirect(url_for('landlord_dashboard'))
            return redirect(url_for('index'))
        return view(**kwargs)
    return wrapped_view


def landlord_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('login'))
        if g.user['role'] != 'owner':
            message = (
                'This section is for Landlord / Lister accounts only. '
                'To list or manage properties, please log out and sign in or register with a separate Landlord account.'
            )
            if request.is_json or request.headers.get('X-CSRF-Token'):
                return jsonify({'error': message}), 403
            flash(message, 'info')
            if g.user['role'] == 'tenant':
                return redirect(url_for('tenant_dashboard'))
            return redirect(url_for('index'))
        return view(**kwargs)
    return wrapped_view

def _home_dashboard_url(user):
    if user['is_admin']:
        return url_for('admin_dashboard')
    if user['role'] == 'owner':
        return url_for('landlord_dashboard')
    return url_for('tenant_dashboard')


@app.before_request
def protect_csrf():
    if request.method not in {'POST', 'PUT', 'PATCH', 'DELETE'}:
        return
    if request.path in {'/webhooks/flutterwave', '/webhooks/resend'}:
        return

    expected_token = session.get('_csrf_token')
    supplied_token = request.form.get('csrf_token') or request.headers.get('X-CSRF-Token')
    if (
        not expected_token
        or not supplied_token
        or not hmac.compare_digest(expected_token, supplied_token)
    ):
        abort(400, description='Your form session expired. Reload the page and try again.')


def csrf_token():
    token = session.get('_csrf_token')
    if token is None:
        token = secrets.token_urlsafe(32)
        session['_csrf_token'] = token
    return token


@app.before_request
def assign_csp_nonce():
    g.csp_nonce = secrets.token_urlsafe(16)


@app.before_request
def enforce_https_in_production():
    if (
        APP_ENV == 'production'
        and not app.testing
        and request.path != '/healthz'
        and not request.is_secure
    ):
        https_url = request.url.replace('http://', 'https://', 1)
        return redirect(https_url, code=301)


@app.before_request
def load_logged_in_user():
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
    else:
        user = get_db().execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        if user is None or user['role'] == 'banned':
            session.clear()
            g.user = None
            if user is not None and user['role'] == 'banned':
                flash('This account has been suspended. Please contact support.', 'error')
        else:
            user_sv = _user_session_version(user)
            stored_sv = session.get('session_version')
            now = time.time()
            last_active = session.get('_session_last_active')
            timeout = (
                ADMIN_SESSION_IDLE_TIMEOUT_SECONDS
                if user['is_admin']
                else SESSION_IDLE_TIMEOUT_SECONDS
            )
            if stored_sv is not None and int(stored_sv) != user_sv:
                session.clear()
                g.user = None
                flash('Your session is no longer valid. Please log in again.', 'info')
            elif last_active is not None and (now - float(last_active)) > timeout:
                session.clear()
                g.user = None
                flash('Your session expired due to inactivity. Please log in again.', 'info')
            else:
                if stored_sv is None:
                    session['session_version'] = user_sv
                session['_session_last_active'] = now
                g.user = user
    expire_pending_booking_requests(get_db())

# --- Routes ---

@app.get('/healthz')
def healthz():
    """Lightweight health check for Render; never exposes configuration or data."""
    try:
        get_db().execute('SELECT 1').fetchone()
    except Exception:
        app.logger.exception('Health check database query failed.')
        return jsonify({'status': 'unhealthy'}), 503
    return jsonify({'status': 'ok'}), 200


def _build_content_security_policy():
    nonce = csp_nonce()
    img_sources = [
        "'self'", 'data:', 'blob:',
        'https://images.unsplash.com',
        'https://*.tile.openstreetmap.org',
        'https://server.arcgisonline.com',
        'https://unpkg.com',
        'https://*.supabase.co',
    ]
    supabase_url = os.getenv('SUPABASE_URL', '').strip()
    if supabase_url:
        parsed = urllib.parse.urlsplit(supabase_url)
        if parsed.scheme == 'https' and parsed.netloc:
            img_sources.append(f'https://{parsed.netloc}')
    return '; '.join([
        "default-src 'self'",
        f"script-src 'self' 'nonce-{nonce}' https://cdn.tailwindcss.com https://unpkg.com",
        f"script-src-elem 'self' 'nonce-{nonce}' https://cdn.tailwindcss.com https://unpkg.com",
        "script-src-attr 'unsafe-inline'",
        "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://fonts.googleapis.com https://unpkg.com",
        "font-src 'self' https://cdnjs.cloudflare.com https://fonts.gstatic.com data:",
        f"img-src {' '.join(dict.fromkeys(img_sources))}",
        "connect-src 'self'",
        "frame-src 'self' https://maps.google.com https://www.google.com",
        "object-src 'none'",
        "base-uri 'self'",
        "frame-ancestors 'self'",
        "form-action 'self' https://checkout.flutterwave.com",
    ])


@app.after_request
def set_security_headers(response):
    response.headers.setdefault('X-Content-Type-Options', 'nosniff')
    response.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
    response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
    response.headers.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=(self)')
    response.headers.setdefault('Content-Security-Policy', _build_content_security_policy())
    if APP_ENV == 'production':
        response.headers.setdefault('Strict-Transport-Security', 'max-age=31536000; includeSubDomains')
    if request.path.startswith('/admin'):
        response.headers.setdefault('X-Robots-Tag', 'noindex, nofollow')
    if (
        request.path.startswith('/admin')
        or request.path.startswith('/tenant/')
        or request.path.startswith('/landlord/')
        or request.path.startswith('/booking/')
        or request.path in ('/support', '/notifications')
    ):
        response.headers.setdefault('Cache-Control', 'no-store, private')
    return response


def _render_error_response(status_code, title, message):
    if not hasattr(g, 'user'):
        g.user = None
    wants_json = (
        request.is_json
        or request.path.startswith('/webhooks/')
        or request.path == '/upload_image'
        or request.accept_mimetypes.best == 'application/json'
    )
    if wants_json:
        return jsonify({'error': message}), status_code
    return render_template(
        'error.html',
        status_code=status_code,
        error_title=title,
        error_message=message,
    ), status_code


@app.errorhandler(400)
def handle_bad_request(error):
    message = getattr(error, 'description', None) or 'The request could not be processed.'
    return _render_error_response(400, 'Bad Request', message)


@app.errorhandler(403)
def handle_forbidden(_error):
    return _render_error_response(403, 'Access Denied', 'You do not have permission to perform this action.')


@app.errorhandler(404)
def handle_not_found(_error):
    return _render_error_response(404, 'Page Not Found', 'The page or resource you requested could not be found.')


@app.errorhandler(413)
def handle_request_too_large(_error):
    return _render_error_response(413, 'Upload Too Large', 'The uploaded file exceeds the maximum permitted size.')


@app.errorhandler(429)
def handle_too_many_requests(error):
    message = getattr(error, 'description', None) or 'Too many requests. Please wait a few minutes and try again.'
    return _render_error_response(429, 'Too Many Requests', message)


@app.errorhandler(500)
def handle_internal_error(_error):
    app.logger.exception('Unhandled application error on %s', request.path)
    return _render_error_response(
        500,
        'Something Went Wrong',
        'An unexpected error occurred while processing your request. Please try again later.',
    )

@app.route('/areas')
def lusaka_areas():
    featured_names = {area['name'] for area in LUSAKA_AREA_GUIDE}
    other_neighbourhoods = [
        name for name in LUSAKA_NEIGHBOURHOODS if name not in featured_names
    ]
    return render_template(
        'areas.html',
        area_guide=LUSAKA_AREA_GUIDE,
        other_neighbourhoods=other_neighbourhoods,
    )


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/terms')
def terms_of_service():
    sections = [
        ('Marketplace role and scope', 'Explain KwachaStay’s role in property discovery, enquiries, and booking connections in Lusaka.'),
        ('Accounts and user responsibilities', 'Set the approved requirements for guest, host, and listing information.'),
        ('Listings and host verification', 'Describe listing standards and the exact meaning and limits of any verification badge.'),
        ('Enquiries, bookings, and payments', 'Explain when a request becomes confirmed and how each enabled payment option works.'),
        ('Cancellations, refunds, and disputes', 'Publish the approved cancellation, refund, and issue-resolution rules.'),
        ('Acceptable use and account actions', 'Specify prohibited conduct and the process for moderation or account restrictions.'),
        ('Contact and effective date', 'Provide the approved business contact details, governing terms, and effective date.'),
    ]
    return render_template('legal.html', page_title='Terms of Service', sections=sections)


@app.route('/privacy')
def privacy_policy():
    sections = [
        ('Information collected', 'List the personal, listing, booking, payment-reference, message, support, and uploaded-photo information the service uses.'),
        ('How information is used', 'Explain use for accounts, property listings, booking coordination, payment verification, support, and platform safety.'),
        ('Service providers and sharing', 'Identify the enabled hosting, payment, email, messaging, and storage providers and what information each receives.'),
        ('Storage, security, and retention', 'Describe where records and uploaded photos are stored, how they are protected, and when they are deleted.'),
        ('User choices and requests', 'Explain how users can access, correct, or request deletion of information and how to contact KwachaStay.'),
        ('Cookies and session data', 'Describe login sessions, security tokens, and any analytics or tracking tools actually enabled.'),
        ('Contact and effective date', 'Provide the approved privacy contact details and effective date.'),
    ]
    return render_template('legal.html', page_title='Privacy Policy', sections=sections)


def _query_listings_context():
    db = get_db()

    near_lat = request.args.get('near_lat', '').strip()
    near_lon = request.args.get('near_lon', '').strip()
    near_radius_km = request.args.get('near_radius_km', '5')
    if near_radius_km not in {'1', '2', '5', '10', '20', '50'}:
        near_radius_km = '5'
    near_point = None
    if near_lat or near_lon:
        try:
            latitude, longitude = float(near_lat), float(near_lon)
            if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
                raise ValueError
            near_point = (latitude, longitude)
            near_lat, near_lon = str(latitude), str(longitude)
        except ValueError:
            near_lat = near_lon = ''
            flash('Choose a valid map location to filter by distance.', 'error')

    # Base query
    query = """
        SELECT p.*, u.profile_pic as owner_pic, u.full_name as owner_name,
               CASE WHEN p.last_confirmed_at IS NOT NULL
                    AND julianday('now') - julianday(p.last_confirmed_at) <= 30
                    THEN 1 ELSE 0 END AS listing_recently_confirmed
        FROM properties p 
        JOIN users u ON p.owner_id = u.id 
        WHERE p.is_active = 1
    """
    params = []
    
    # Keyword Search
    search_q = request.args.get('q', '').strip()
    if search_q:
        query += " AND (p.title LIKE ? OR p.description LIKE ? OR p.compound LIKE ? OR p.location_details LIKE ? OR p.agent_name LIKE ?)"
        like = f'%{search_q}%'
        params.extend([like, like, like, like, like])
    
    # Filtering logic
    compound = request.args.get('compound')
    if compound and compound != 'All':
        query += " AND p.compound = ?"
        params.append(compound)

    if near_point:
        query += ''' AND p.latitude IS NOT NULL AND p.longitude IS NOT NULL
                     AND distance_km(p.latitude, p.longitude, ?, ?) <= ?'''
        params.extend([near_point[0], near_point[1], float(near_radius_km)])

    # Advanced filters (validated to avoid type errors on SQLite and PostgreSQL)
    def _parse_optional_float(raw):
        raw = (raw or '').strip()
        if not raw:
            return None
        try:
            val = float(raw)
            return val if math.isfinite(val) and val >= 0 else None
        except ValueError:
            return None

    def _parse_optional_int(raw):
        raw = (raw or '').strip()
        if not raw:
            return None
        try:
            val = int(raw)
            return val if 0 <= val <= 100 else None
        except ValueError:
            return None

    min_price = _parse_optional_float(request.args.get('min_price'))
    max_price = _parse_optional_float(request.args.get('max_price'))
    property_type = request.args.get('property_type')
    listing_category = request.args.get('listing_category')
    availability_status = request.args.get('availability_status')
    min_bedrooms = _parse_optional_int(request.args.get('min_bedrooms'))
    max_bedrooms = _parse_optional_int(request.args.get('max_bedrooms'))
    min_bathrooms = _parse_optional_int(request.args.get('min_bathrooms'))
    max_bathrooms = _parse_optional_int(request.args.get('max_bathrooms'))
    verified_only = request.args.get('verified_only')
    featured_only = request.args.get('featured_only')
    power_backup = request.args.get('power_backup', '')
    water_supply = request.args.get('water_supply', '')
    if power_backup not in POWER_BACKUP_OPTIONS:
        power_backup = ''
    if water_supply not in WATER_SUPPLY_OPTIONS:
        water_supply = ''
    
    if min_price is not None:
        query += " AND p.price_per_night >= ?"
        params.append(min_price)

    if max_price is not None:
        query += " AND p.price_per_night <= ?"
        params.append(max_price)
        
    if property_type and property_type != 'All':
        query += " AND p.property_type = ?"
        params.append(property_type)

    if power_backup:
        query += " AND p.power_backup = ?"
        params.append(power_backup)

    if water_supply:
        query += " AND p.water_supply = ?"
        params.append(water_supply)

    if listing_category and listing_category != 'All':
        query += " AND p.listing_category = ?"
        params.append(listing_category)

    if availability_status and availability_status != 'All':
        query += " AND p.availability_status = ?"
        params.append(availability_status)

    if min_bedrooms:
        query += " AND p.bedrooms >= ?"
        params.append(min_bedrooms)

    if max_bedrooms:
        query += " AND p.bedrooms <= ?"
        params.append(max_bedrooms)

    if min_bathrooms:
        query += " AND p.bathrooms >= ?"
        params.append(min_bathrooms)

    if max_bathrooms:
        query += " AND p.bathrooms <= ?"
        params.append(max_bathrooms)

    if verified_only:
        query += " AND p.is_verified = 1"

    if featured_only:
        query += " AND p.is_featured = 1"

    # Amenities Checkboxes
    amenities = ['has_solar', 'has_borehole', 'has_pool', 'has_wifi', 'has_ac', 'has_parking']
    for amenity in amenities:
        if request.args.get(amenity):
            query += f" AND p.{amenity} = 1"

    # Sort
    sort = request.args.get('sort', 'newest')
    if sort == 'price_asc':
        query += " ORDER BY p.price_per_night ASC"
    elif sort == 'price_desc':
        query += " ORDER BY p.price_per_night DESC"
    elif sort == 'distance' and near_point:
        query += " ORDER BY distance_km(p.latitude, p.longitude, ?, ?) ASC"
        params.extend(near_point)
    elif sort == 'top_rated':
        query = f"""
            SELECT p.*, u.profile_pic as owner_pic, u.full_name as owner_name,
                   (SELECT AVG(r2.rating) FROM reviews r2 WHERE r2.property_id = p.id) as avg_r
            FROM properties p
            JOIN users u ON p.owner_id = u.id
            WHERE p.is_active = 1
        """
        params = []
        if search_q:
            query += " AND (p.title LIKE ? OR p.description LIKE ? OR p.compound LIKE ? OR p.location_details LIKE ? OR p.agent_name LIKE ?)"
            like = f'%{search_q}%'
            params.extend([like, like, like, like, like])
        if compound and compound != 'All':
            query += " AND p.compound = ?"
            params.append(compound)
        if near_point:
            query += ''' AND p.latitude IS NOT NULL AND p.longitude IS NOT NULL
                         AND distance_km(p.latitude, p.longitude, ?, ?) <= ?'''
            params.extend([near_point[0], near_point[1], float(near_radius_km)])
        if min_price:
            query += " AND p.price_per_night >= ?"
            params.append(min_price)
        if max_price:
            query += " AND p.price_per_night <= ?"
            params.append(max_price)
        if property_type and property_type != 'All':
            query += " AND p.property_type = ?"
            params.append(property_type)
        if power_backup:
            query += " AND p.power_backup = ?"
            params.append(power_backup)
        if water_supply:
            query += " AND p.water_supply = ?"
            params.append(water_supply)
        if listing_category and listing_category != 'All':
            query += " AND p.listing_category = ?"
            params.append(listing_category)
        if availability_status and availability_status != 'All':
            query += " AND p.availability_status = ?"
            params.append(availability_status)
        if min_bedrooms:
            query += " AND p.bedrooms >= ?"
            params.append(min_bedrooms)
        if max_bedrooms:
            query += " AND p.bedrooms <= ?"
            params.append(max_bedrooms)
        if min_bathrooms:
            query += " AND p.bathrooms >= ?"
            params.append(min_bathrooms)
        if max_bathrooms:
            query += " AND p.bathrooms <= ?"
            params.append(max_bathrooms)
        if verified_only:
            query += " AND p.is_verified = 1"
        if featured_only:
            query += " AND p.is_featured = 1"
        for amenity in amenities:
            if request.args.get(amenity):
                query += f" AND p.{amenity} = 1"
        query += " ORDER BY avg_r DESC"
    elif sort == 'most_viewed':
        query += " ORDER BY p.view_count DESC"
    elif sort == 'featured':
        query += " ORDER BY p.is_featured DESC, p.created_at DESC"
    else:  # newest
        query += " ORDER BY p.created_at DESC"
    
    # --- Pagination ---
    PER_PAGE = 12
    try:
        page = max(1, min(10000, int(request.args.get('page', 1))))
    except (TypeError, ValueError):
        page = 1
    
    # Total count for pagination
    count_query = f"SELECT COUNT(*) FROM ({query}) sub"
    total = db.execute(count_query, params).fetchone()[0]
    total_pages = max(1, -(-total // PER_PAGE))  # ceiling division
    
    paginated_query = query + f" LIMIT {PER_PAGE} OFFSET {(page-1)*PER_PAGE}"
    properties_raw = db.execute(paginated_query, params).fetchall()
    
    # Fetch additional data for properties (Images, Reviews)
    properties = []
    map_markers = []
    for prop in properties_raw:
        prop_dict = dict(prop)
        if near_point and prop['latitude'] is not None and prop['longitude'] is not None:
            prop_dict['distance_km'] = round(
                distance_km(*near_point, prop['latitude'], prop['longitude']), 1
            )
        if prop['latitude'] is not None and prop['longitude'] is not None:
            map_markers.append({
                'id': prop['id'],
                'title': prop['title'],
                'price': prop['price_per_night'],
                'latitude': prop['latitude'],
                'longitude': prop['longitude'],
            })
        
        # Get Images (always prioritize the main photo first, skipping missing local files)
        imgs = db.execute("SELECT image_url FROM property_images WHERE property_id = ?", (prop['id'],)).fetchall()
        def _listing_img_ok(u):
            if not u:
                return False
            if u.startswith('/static/uploads/'):
                return os.path.isfile(os.path.join(BASE_DIR, u.lstrip('/').replace('/', os.sep)))
            return True
        extra_img_urls = [i['image_url'] for i in imgs if _listing_img_ok(i['image_url'])]
        if _listing_img_ok(prop['image_main']):
            prop_dict['images'] = [prop['image_main']] + [u for u in extra_img_urls if u != prop['image_main']]
        else:
            prop_dict['images'] = extra_img_urls
             
        # Get Review Stats
        stats = db.execute("SELECT AVG(rating) as avg_rating, COUNT(id) as count FROM reviews WHERE property_id = ?", (prop['id'],)).fetchone()
        prop_dict['rating'] = round(stats['avg_rating'], 1) if stats['avg_rating'] else None
        prop_dict['review_count'] = stats['count']
        
        properties.append(prop_dict)
    
    # Stats for banner
    total_active = db.execute("SELECT COUNT(*) FROM properties WHERE is_active = 1").fetchone()[0]
    total_compounds = db.execute("SELECT COUNT(DISTINCT compound) FROM properties WHERE is_active = 1").fetchone()[0]

    return dict(
        properties=properties,
        compounds=LUSAKA_NEIGHBOURHOODS,
        selected_compound=compound,
        search_q=search_q,
        page=page,
        total_pages=total_pages,
        total_active=total_active,
        total_compounds=total_compounds,
        sort=sort,
        listing_category=listing_category,
        availability_status=availability_status,
        verified_only=bool(verified_only),
        featured_only=bool(featured_only),
        property_type=property_type,
        min_price=min_price,
        max_price=max_price,
        min_bedrooms=min_bedrooms,
        max_bedrooms=max_bedrooms,
        min_bathrooms=min_bathrooms,
        max_bathrooms=max_bathrooms,
        power_backup=power_backup,
        water_supply=water_supply,
        power_backup_options=POWER_BACKUP_OPTIONS,
        water_supply_options=WATER_SUPPLY_OPTIONS,
        near_lat=near_lat,
        near_lon=near_lon,
        near_point=near_point,
        near_radius_km=near_radius_km,
        map_markers=map_markers,
    )


@app.route('/')
def index():
    if g.user is not None:
        return redirect(_home_dashboard_url(g.user))
    return render_template('index.html', **_query_listings_context())


@app.route('/stays')
@tenant_required
def browse_stays():
    return render_template('browse_stays.html', **_query_listings_context())

@app.route('/signup', methods=('GET', 'POST'))
def signup():
    if g.user is not None:
        return redirect(_home_dashboard_url(g.user))
    if request.method == 'POST':
        if not check_rate_limit('signup_ip', client_ip(), 10, 3600):
            abort(429, description='Too many registration attempts. Please try again later.')
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        phone_raw = request.form.get('phone', '').strip()
        country_code = request.form.get('country_code', '').strip()
        country_region = request.form.get('country_region', 'ZM').upper()
        password = request.form.get('password', '')
        role = request.form.get('role', 'tenant')
        db = get_db()
        password_error = validate_password_strength(password)

        if not full_name or len(full_name) > 120:
            flash('Enter a valid full name (up to 120 characters).', 'error')
        elif not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', email) or len(email) > 254:
            flash('Enter a valid email address.', 'error')
        elif role not in ('tenant', 'owner'):
            flash('Choose either a guest or host account.', 'error')
        elif password_error:
            flash(password_error, 'error')
        else:
            phone_input = (
                f'{country_code}{phone_raw}'
                if phone_raw and not phone_raw.startswith('+') and country_code.startswith('+')
                else phone_raw
            )
            try:
                full_phone = normalize_phone_number(phone_input, country_region)
            except ValueError as error:
                flash(str(error), 'error')
            else:
                try:
                    is_configured_admin = 1 if email in ADMIN_EMAILS else 0
                    db.execute(
                        '''INSERT INTO users (full_name, email, phone, password, role, is_admin)
                           VALUES (?, ?, ?, ?, ?, ?)''',
                        (full_name, email, full_phone, generate_password_hash(password), role, is_configured_admin),
                    )
                    db.commit()
                except DB_INTEGRITY_ERRORS:
                    db.rollback()
                    flash('An account already uses that email address.', 'error')
                else:
                    flash('Account created successfully! Please log in with your email or phone and password.', 'success')
                    return redirect(url_for('login'))

    default_role = request.args.get('role', 'tenant')
    if default_role not in ('tenant', 'owner'):
        default_role = 'tenant'
    return render_template('signup.html', phone_countries=phone_country_options(), default_role=default_role)


@app.route('/saved-searches/save', methods=['POST'])
@tenant_required
def save_search():
    db = get_db()
    existing_count = db.execute(
        'SELECT COUNT(*) FROM saved_searches WHERE user_id = ?', (g.user['id'],)
    ).fetchone()[0]
    if existing_count >= 10:
        flash('You can save up to 10 searches. Remove one before saving another.', 'error')
        return safe_redirect_referrer('browse_stays')

    try:
        min_price = float(request.form['min_price']) if request.form.get('min_price', '').strip() else None
        max_price = float(request.form['max_price']) if request.form.get('max_price', '').strip() else None
    except ValueError:
        flash('Price filters must be valid numbers to save this search.', 'error')
        return safe_redirect_referrer('browse_stays')
    if ((min_price is not None and min_price < 0)
            or (max_price is not None and max_price < 0)
            or (min_price is not None and max_price is not None and min_price > max_price)):
        flash('Enter a valid minimum and maximum price to save this search.', 'error')
        return safe_redirect_referrer('browse_stays')

    power_backup = request.form.get('power_backup', '').strip()
    water_supply = request.form.get('water_supply', '').strip()
    if power_backup not in ('', 'All', *POWER_BACKUP_OPTIONS):
        flash('Choose a valid power backup filter.', 'error')
        return safe_redirect_referrer('browse_stays')
    if water_supply not in ('', 'All', *WATER_SUPPLY_OPTIONS):
        flash('Choose a valid water supply filter.', 'error')
        return safe_redirect_referrer('browse_stays')

    near_lat_raw = request.form.get('near_lat', '').strip()
    near_lon_raw = request.form.get('near_lon', '').strip()
    near_radius_km = request.form.get('near_radius_km', '').strip()
    near_lat = near_lon = None
    if bool(near_lat_raw) != bool(near_lon_raw):
        flash('Choose a complete map location before saving this search.', 'error')
        return safe_redirect_referrer('browse_stays')
    if near_lat_raw:
        try:
            near_lat, near_lon = float(near_lat_raw), float(near_lon_raw)
        except ValueError:
            flash('Choose a valid map location before saving this search.', 'error')
            return safe_redirect_referrer('browse_stays')
        if (not -90 <= near_lat <= 90 or not -180 <= near_lon <= 180
                or near_radius_km not in {'1', '2', '5', '10', '20', '50'}):
            flash('Choose a valid map location and distance before saving this search.', 'error')
            return safe_redirect_referrer('browse_stays')
        near_radius_km = float(near_radius_km)
    else:
        near_radius_km = None

    db.execute(
        '''INSERT INTO saved_searches
           (user_id, search_query, compound, min_price, max_price, property_type,
            power_backup, water_supply, near_lat, near_lon, near_radius_km)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (g.user['id'], request.form.get('q', '').strip() or None,
         request.form.get('compound', '').strip() or None,
         min_price, max_price,
         request.form.get('property_type', '').strip() or None,
         power_backup if power_backup not in ('', 'All') else None,
         water_supply if water_supply not in ('', 'All') else None,
         near_lat, near_lon, near_radius_km),
    )
    db.commit()
    flash('Search saved. We’ll notify you when matching listings are added, repriced, or relisted.', 'success')
    return safe_redirect_referrer('browse_stays')


@app.route('/saved-searches/delete/<int:search_id>', methods=['POST'])
@tenant_required
def delete_saved_search(search_id):
    db = get_db()
    db.execute('DELETE FROM saved_searches WHERE id = ? AND user_id = ?',
               (search_id, g.user['id']))
    db.commit()
    flash('Saved search removed.', 'info')
    return redirect(url_for('dashboard'))


@app.route('/trip-plans/create', methods=['POST'])
@tenant_required
def create_trip_plan():
    selected_ids = request.form.getlist('property_ids')
    try:
        property_ids = list(dict.fromkeys(int(value) for value in selected_ids))
    except (TypeError, ValueError):
        flash('Choose valid saved properties for your trip plan.', 'error')
        return redirect(url_for('dashboard'))
    if not 2 <= len(property_ids) <= 4:
        flash('Choose between 2 and 4 saved properties to compare.', 'error')
        return redirect(url_for('dashboard'))

    db = get_db()
    placeholders = ','.join('?' for _ in property_ids)
    saved = db.execute(
        f'''SELECT w.property_id FROM wishlists w
            JOIN properties p ON p.id = w.property_id AND p.is_active = 1
            WHERE w.user_id = ? AND w.property_id IN ({placeholders})''',
        [g.user['id'], *property_ids],
    ).fetchall()
    if len(saved) != len(property_ids):
        flash('Trip plans can only include your currently saved, active listings.', 'error')
        return redirect(url_for('dashboard'))

    name = request.form.get('name', '').strip()[:80] or 'My Lusaka shortlist'
    try:
        db.execute('BEGIN IMMEDIATE')
        token = secrets.token_urlsafe(24)
        cursor = db.execute(
            'INSERT INTO trip_plans (user_id, share_token, name) VALUES (?, ?, ?)',
            (g.user['id'], token, name),
        )
        db.executemany(
            'INSERT INTO trip_plan_items (trip_plan_id, property_id) VALUES (?, ?)',
            [(cursor.lastrowid, property_id) for property_id in property_ids],
        )
        db.commit()
    except DB_ERRORS:
        db.rollback()
        app.logger.exception('Could not create trip plan for user %s', g.user['id'])
        flash('Could not create your trip plan. Please try again.', 'error')
        return redirect(url_for('dashboard'))
    flash('Shareable trip plan created.', 'success')
    return redirect(url_for('shared_trip_plan', share_token=token))


@app.route('/trip/<share_token>')
def shared_trip_plan(share_token):
    db = get_db()
    plan = db.execute(
        'SELECT id, name, created_at FROM trip_plans WHERE share_token = ?',
        (share_token,),
    ).fetchone()
    if not plan:
        flash('Trip plan not found.', 'error')
        return redirect(url_for('index'))
    properties = db.execute(
        '''SELECT p.*,
                  (SELECT AVG(r.rating) FROM reviews r WHERE r.property_id = p.id) AS avg_rating,
                  (SELECT COUNT(*) FROM reviews r WHERE r.property_id = p.id) AS review_count
           FROM trip_plan_items tpi
           JOIN properties p ON p.id = tpi.property_id
           WHERE tpi.trip_plan_id = ? AND p.is_active = 1
           ORDER BY tpi.created_at''',
        (plan['id'],),
    ).fetchall()
    return render_template('trip_plan.html', plan=plan, properties=properties)


@app.route('/property/<int:property_id>/report', methods=['POST'])
@login_required
def report_property(property_id):
    if not check_rate_limit('report_property_user', str(g.user['id']), 10, 3600):
        abort(429, description='Too many listing reports submitted. Please try again later.')
    db = get_db()
    property_row = db.execute(
        'SELECT id, owner_id FROM properties WHERE id = ?', (property_id,)
    ).fetchone()
    if not property_row:
        flash('Listing not found.', 'error')
        return redirect(url_for('index'))
    if property_row['owner_id'] == g.user['id']:
        flash('You cannot report your own listing.', 'error')
        return redirect(url_for('property_details', property_id=property_id))

    reason = request.form.get('reason', '').strip()
    details = request.form.get('details', '').strip()
    allowed_reasons = {
        'Incorrect or misleading information',
        'Suspicious or fraudulent listing',
        'Inappropriate content',
        'Other',
    }
    if reason not in allowed_reasons:
        flash('Choose a valid reason for the report.', 'error')
        return redirect(url_for('property_details', property_id=property_id))

    open_report = db.execute(
        '''SELECT id FROM property_reports
           WHERE property_id = ? AND reporter_id = ? AND status = 'open' LIMIT 1''',
        (property_id, g.user['id']),
    ).fetchone()
    if open_report:
        flash('You already have an open report for this listing.', 'info')
        return redirect(url_for('property_details', property_id=property_id))

    db.execute(
        'INSERT INTO property_reports (property_id, reporter_id, reason, details) VALUES (?, ?, ?, ?)',
        (property_id, g.user['id'], reason, details[:2000] or None),
    )
    db.commit()
    flash('Report sent to the KwachaStay team for review.', 'success')
    return redirect(url_for('property_details', property_id=property_id))


@app.route('/support', methods=['GET', 'POST'])
@login_required
def support_center():
    db = get_db()
    booking_id = request.values.get('booking_id', '').strip()
    if booking_id:
        try:
            booking_id = int(booking_id)
        except ValueError:
            flash('Choose a valid booking.', 'error')
            return redirect(url_for('support_center'))

    booking = None
    if booking_id:
        booking = db.execute(
            '''SELECT b.id FROM bookings b
               JOIN properties p ON p.id = b.property_id
               WHERE b.id = ? AND (b.user_id = ? OR p.owner_id = ?)''',
            (booking_id, g.user['id'], g.user['id']),
        ).fetchone()
        if not booking:
            flash('That booking was not found or is not associated with your account.', 'error')
            return redirect(url_for('support_center'))

    if request.method == 'POST':
        if not check_rate_limit('support_request_user', str(g.user['id']), 10, 3600):
            abort(429, description='Too many support requests submitted. Please try again later.')
        category = request.form.get('category', '').strip()
        details = request.form.get('details', '').strip()
        if category not in SUPPORT_CATEGORIES:
            flash('Choose a support topic.', 'error')
        elif len(details) < 10 or len(details) > 3000:
            flash('Please describe the issue in 10 to 3,000 characters.', 'error')
        else:
            db.execute(
                '''INSERT INTO support_requests (reporter_id, booking_id, category, details)
                   VALUES (?, ?, ?, ?)''',
                (g.user['id'], booking_id or None, category, details),
            )
            request_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
            admins = db.execute('SELECT id FROM users WHERE is_admin = 1').fetchall()
            for admin in admins:
                create_notification(
                    db, admin['id'],
                    f'New support request #{request_id}: {SUPPORT_CATEGORIES[category]}.',
                    url_for('admin_dashboard'),
                )
            db.commit()
            flash('Your request has been sent to KwachaStay support.', 'success')
            return redirect(url_for('support_center'))

    bookings = db.execute(
        '''SELECT b.id, b.tx_ref, b.check_in, b.check_out, p.title
           FROM bookings b
           JOIN properties p ON p.id = b.property_id
           WHERE b.user_id = ? OR p.owner_id = ?
           ORDER BY b.created_at DESC LIMIT 50''',
        (g.user['id'], g.user['id']),
    ).fetchall()
    requests = db.execute(
        '''SELECT sr.*, b.tx_ref, p.title AS property_title
           FROM support_requests sr
           LEFT JOIN bookings b ON b.id = sr.booking_id
           LEFT JOIN properties p ON p.id = b.property_id
           WHERE sr.reporter_id = ?
           ORDER BY sr.created_at DESC''',
        (g.user['id'],),
    ).fetchall()
    return render_template(
        'support.html', bookings=bookings, support_requests=requests,
        selected_booking_id=booking_id or '',
        support_categories=SUPPORT_CATEGORIES,
    )


@app.route('/host/verification/request', methods=['POST'])
@landlord_required
def request_host_verification():
    if g.user['role'] != 'owner':
        flash('Only host accounts can request host verification.', 'error')
        return redirect(url_for('dashboard'))
    note = request.form.get('verification_note', '').strip()
    db = get_db()
    current = db.execute(
        'SELECT host_verification_status FROM users WHERE id = ?', (g.user['id'],)
    ).fetchone()
    if current['host_verification_status'] == 'verified':
        flash('Your host account is already verified.', 'info')
    elif current['host_verification_status'] == 'pending':
        flash('Your verification request is already being reviewed.', 'info')
    else:
        db.execute(
            '''UPDATE users
               SET host_verification_status = 'pending', host_verification_note = ?
               WHERE id = ?''',
            (note[:1000] or None, g.user['id']),
        )
        db.commit()
        flash('Verification request submitted. The team will review it before granting a badge.', 'success')
    return redirect(url_for('dashboard'))


@app.route('/booking/<int:booking_id>/refund-request', methods=['POST'])
@tenant_required
def request_refund(booking_id):
    db = get_db()
    booking = db.execute(
        'SELECT id, payment_status, refund_status, booking_status FROM bookings WHERE id = ? AND user_id = ?',
        (booking_id, g.user['id']),
    ).fetchone()
    if not booking:
        flash('Booking not found or unauthorized.', 'error')
        return redirect(url_for('dashboard'))
    if booking['payment_status'] != 'paid':
        flash('A refund can only be requested for a payment verified as paid.', 'error')
    elif booking['refund_status'] not in (None, 'none', 'rejected'):
        flash('A refund request is already being processed or has been completed.', 'info')
    else:
        db.execute("UPDATE bookings SET refund_status = 'requested' WHERE id = ?", (booking_id,))
        db.commit()
        flash('Refund request sent. The payment team will review it against the cancellation policy.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/login', methods=('GET', 'POST'))
def login():
    if g.user is not None:
        return redirect(_home_dashboard_url(g.user))
    if request.method == 'POST':
        identifier = (request.form.get('identifier') or request.form.get('email') or '').strip()
        password = request.form.get('password', '')
        ip_key = client_ip()
        id_key = identifier.lower()[:128] or 'empty'
        if (
            is_rate_limited('login_fail_ip', ip_key, 10, 900)
            or is_rate_limited('login_fail_id', f'{ip_key}:{id_key}', 5, 900)
        ):
            abort(429, description='Too many failed login attempts. Please wait 15 minutes and try again.')
        db = get_db()
        user = None
        if '@' in identifier:
            user = db.execute(
                'SELECT * FROM users WHERE LOWER(email) = ?', (identifier.lower(),)
            ).fetchone()
        elif identifier:
            try:
                phone = normalize_phone_number(
                    identifier, request.form.get('country_region', 'ZM').upper()
                )
            except ValueError:
                user = None
            else:
                user = db.execute(
                    '''SELECT * FROM users
                       WHERE phone = ? OR REPLACE(phone, ' ', '') = ? LIMIT 1''',
                    (phone, phone),
                ).fetchone()

        if user is None or not check_password_hash(user['password'], password):
            record_rate_limit_hit('login_fail_ip', ip_key, 900)
            record_rate_limit_hit('login_fail_id', f'{ip_key}:{id_key}', 900)
            flash('The email/phone or password is incorrect.', 'error')
        elif user['role'] == 'banned':
            flash('This account has been suspended. Please contact support.', 'error')
        else:
            reset_rate_limit('login_fail_id', f'{ip_key}:{id_key}')
            is_admin_user = bool(user['is_admin'])
            if (user['email'] or '').strip().lower() in ADMIN_EMAILS and not is_admin_user:
                db.execute('UPDATE users SET is_admin = 1 WHERE id = ?', (user['id'],))
                log_admin_action(
                    db,
                    'admin_auto_promoted',
                    target_type='user',
                    target_id=user['id'],
                    details='Promoted via ADMIN_EMAILS configuration on login',
                    admin_user=user,
                )
                db.commit()
                is_admin_user = True
            if is_admin_user and _user_totp_enabled(user):
                session.clear()
                session['pending_2fa_user_id'] = user['id']
                session['pending_2fa_expires'] = time.time() + 300
                session['pending_2fa_remember'] = bool(request.form.get('remember_me'))
                csrf_token()
                return redirect(url_for('admin_verify_2fa'))
            session.clear()
            now = time.time()
            session['user_id'] = user['id']
            session['session_version'] = _user_session_version(user)
            session['_session_created_at'] = now
            session['_session_last_active'] = now
            session.permanent = bool(request.form.get('remember_me'))
            csrf_token()
            flash(f"Welcome back, {user['full_name']}!", 'success')
            if is_admin_user:
                return redirect(url_for('admin_dashboard'))
            if user['role'] == 'owner':
                return redirect(url_for('landlord_dashboard'))
            return redirect(url_for('tenant_dashboard'))

    return render_template('login.html', phone_countries=phone_country_options())


@app.route('/admin/verify-2fa', methods=('GET', 'POST'))
def admin_verify_2fa():
    pending_uid = session.get('pending_2fa_user_id')
    pending_exp = session.get('pending_2fa_expires') or 0
    if not pending_uid or time.time() > float(pending_exp):
        session.pop('pending_2fa_user_id', None)
        session.pop('pending_2fa_expires', None)
        session.pop('pending_2fa_remember', None)
        flash('Two-factor authentication session expired. Please log in again.', 'error')
        return redirect(url_for('login'))

    db = get_db()
    user = db.execute('SELECT * FROM users WHERE id = ?', (pending_uid,)).fetchone()
    if not user or not user['is_admin'] or user['role'] == 'banned' or not _user_totp_enabled(user):
        session.clear()
        return redirect(url_for('login'))

    if request.method == 'POST':
        rate_key = f'{client_ip()}:{pending_uid}'
        if is_rate_limited('admin_2fa_fail', rate_key, 5, 600):
            abort(429, description='Too many invalid authenticator codes. Please wait 10 minutes and try again.')
        code = request.form.get('totp_code', '').strip()
        if not verify_totp_code(user['totp_secret'], code):
            record_rate_limit_hit('admin_2fa_fail', rate_key, 600)
            flash('Invalid authenticator code. Please try again.', 'error')
            return render_template('admin_verify_2fa.html')
        reset_rate_limit('admin_2fa_fail', rate_key)
        remember = bool(session.get('pending_2fa_remember'))
        session.clear()
        now = time.time()
        session['user_id'] = user['id']
        session['session_version'] = _user_session_version(user)
        session['_session_created_at'] = now
        session['_session_last_active'] = now
        session.permanent = remember
        csrf_token()
        log_admin_action(db, 'admin_2fa_login_verified', 'user', user['id'], admin_user=user)
        db.commit()
        flash(f"Welcome back, {user['full_name']}!", 'success')
        return redirect(url_for('admin_dashboard'))

    return render_template('admin_verify_2fa.html')

@app.route('/logout', methods=['GET', 'POST'])
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('index'))

@app.route('/add_house', methods=('GET', 'POST'))
@landlord_required
def add_house():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        price_raw = request.form.get('price', '').strip()
        compound = request.form.get('compound', '').strip()
        property_type = request.form.get('property_type', '').strip()
        price_period_raw = request.form.get('price_period', '').strip().lower()
        price_period = price_period_raw if price_period_raw in ('night', 'month') else default_price_period_for_type(property_type)
        if not title or not description or not compound or not property_type:
            flash('Please fill in all required property details.', 'error')
            return redirect(url_for('add_house'))
        if len(title) > 160 or len(description) > 5000:
            flash('Title must be under 160 characters and description under 5,000 characters.', 'error')
            return redirect(url_for('add_house'))
        try:
            price = parse_nonnegative_money(price_raw, 'Price')
            if price <= 0:
                raise ValueError('Price must be greater than zero.')
        except ValueError as error:
            flash(str(error), 'error')
            return redirect(url_for('add_house'))
        try:
            latitude, longitude = parse_location_coordinates(
                request.form.get('latitude'), request.form.get('longitude')
            )
            utility_fields = parse_property_utility_fields(request.form)
            checkin_fields = parse_checkin_fields(request.form, is_long_term=(price_period == 'month'))
            stay_terms = parse_stay_terms_fields(request.form, property_type, price_period)
        except ValueError as error:
            flash(str(error), 'error')
            return redirect(url_for('add_house'))
        cancellation_policy = request.form.get('cancellation_policy', 'moderate')
        house_rules = request.form.get('house_rules', '').strip()
        arrival_instructions = request.form.get('arrival_instructions', '').strip()
        arrival_directions = request.form.get('arrival_directions', '').strip()
        nearby_essentials = request.form.get('nearby_essentials', '').strip()
        main_photo_category = request.form.get('main_photo_category', 'other')
        try:
            cleaning_fee = parse_nonnegative_money(request.form.get('cleaning_fee'), 'Cleaning fee')
            refundable_deposit = parse_nonnegative_money(request.form.get('refundable_deposit'), 'Refundable deposit')
        except ValueError as error:
            flash(str(error), 'error')
            return redirect(url_for('add_house'))
        if (cancellation_policy not in ('flexible', 'moderate', 'strict')
                or len(house_rules) > 2000 or len(arrival_instructions) > 3000
                or len(arrival_directions) > 1000 or len(nearby_essentials) > 1000
                or main_photo_category not in PHOTO_CATEGORIES):
            flash('Choose a valid cancellation policy and keep house rules under 2,000 characters.', 'error')
            return redirect(url_for('add_house'))
        listing_category = request.form.get('listing_category', 'rental')
        availability_status = request.form.get('availability_status', 'available')
        location_details = request.form.get('location_details', '').strip()
        agent_name = request.form.get('agent_name', '').strip()
        agent_phone = request.form.get('agent_phone', '').strip()
        try:
            bedrooms = max(1, int(request.form.get('bedrooms') or 1))
            bathrooms = max(1, int(request.form.get('bathrooms') or 1))
        except ValueError:
            flash('Bedrooms and bathrooms must be whole numbers.', 'error')
            return redirect(url_for('add_house'))
        is_featured = 1 if (g.user['is_admin'] and request.form.get('is_featured') == 'on') else 0
        
        # Details
        bed_type = request.form.get('bed_type')
        room_capacity = request.form.get('room_capacity')
        kitchen_type = request.form.get('kitchen_type')
        
        # Amenities (Checkbox handling)
        has_sitting_room = 1 if 'has_sitting_room' in request.form else 0
        has_solar = 1 if 'has_solar' in request.form else 0
        has_borehole = 1 if 'has_borehole' in request.form else 0
        has_pool = 1 if 'has_pool' in request.form else 0
        has_garden = 1 if 'has_garden' in request.form else 0
        has_bbq = 1 if 'has_bbq' in request.form else 0
        has_balcony = 1 if 'has_balcony' in request.form else 0
        has_ac = 1 if 'has_ac' in request.form else 0
        has_wifi = 1 if 'has_wifi' in request.form else 0
        has_parking = 1 if 'has_parking' in request.form else 0
        
        image_url_raw = request.form.get('image_url', '').strip()
        if not image_url_raw:
            flash('Please upload a main photo before listing your property.', 'error')
            return redirect(url_for('add_house'))
        try:
            image_url = validate_image_url(image_url_raw)
            validated_extra_images = []
            extra_images = request.form.get('extra_images', '')
            if extra_images.strip():
                for img in extra_images.split(','):
                    img = img.strip()
                    if img:
                        validated_extra_images.append(validate_image_url(img))
        except ValueError as error:
            flash(str(error), 'error')
            return redirect(url_for('add_house'))
        extra_categories = request.form.get('extra_image_categories', '').split(',')
        owner_id = g.user['id']
        
        db = get_db()
        cursor = db.execute(
            '''INSERT INTO properties (
                owner_id, title, description, price_per_night, price_period, compound, property_type,
                listing_category, availability_status, location_details, agent_name, agent_phone,
                bedrooms, bathrooms, bed_type, room_sharing, room_capacity, kitchen_type, has_sitting_room,
                upfront_months, hourly_rate,
                has_solar, has_borehole, has_pool, has_garden, has_bbq,
                has_balcony, has_ac, has_wifi, has_parking, image_main, is_featured,
                cancellation_policy, house_rules, cleaning_fee, refundable_deposit,
                utilities_included, power_backup, water_supply, internet_availability,
                internet_speed_mbps, emergency_contact_name, emergency_contact_phone,
                arrival_instructions, arrival_directions, nearby_essentials,
                checkin_time, checkout_time, self_checkin_method,
                main_photo_category, latitude, longitude
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (owner_id, title, description, price, price_period, compound, property_type,
             listing_category, availability_status, location_details, agent_name, agent_phone,
             bedrooms, bathrooms, bed_type, stay_terms['room_sharing'], room_capacity, kitchen_type, has_sitting_room,
             stay_terms['upfront_months'], stay_terms['hourly_rate'],
             has_solar, has_borehole, has_pool, has_garden, has_bbq,
             has_balcony, has_ac, has_wifi, has_parking, image_url, is_featured,
             cancellation_policy, house_rules, cleaning_fee, refundable_deposit,
             1 if request.form.get('utilities_included') == 'on' else 0,
             utility_fields['power_backup'], utility_fields['water_supply'],
             utility_fields['internet_availability'], utility_fields['internet_speed_mbps'],
             utility_fields['emergency_contact_name'], utility_fields['emergency_contact_phone'],
             arrival_instructions, arrival_directions, nearby_essentials,
             checkin_fields['checkin_time'], checkin_fields['checkout_time'],
             checkin_fields['self_checkin_method'], main_photo_category,
             latitude, longitude)
        )
        prop_id = cursor.lastrowid
        notify_matching_searches(
            db,
            db.execute('SELECT * FROM properties WHERE id = ?', (prop_id,)).fetchone(),
        )
        
        if validated_extra_images:
            for index, img in enumerate(validated_extra_images):
                category = extra_categories[index] if index < len(extra_categories) else 'other'
                if category not in PHOTO_CATEGORIES:
                    category = 'other'
                db.execute(
                    'INSERT INTO property_images (property_id, image_url, category) VALUES (?, ?, ?)',
                    (prop_id, img, category),
                )
        
        db.commit()
        flash('Property listed successfully!', 'success')
        return redirect(url_for('landlord_dashboard'))
        
    return render_template(
        'add_house.html',
        compounds=LUSAKA_NEIGHBOURHOODS,
        neighbourhood_coords=LUSAKA_NEIGHBOURHOOD_COORDS,
        photo_categories=PHOTO_CATEGORIES,
        power_backup_options=POWER_BACKUP_OPTIONS,
        water_supply_options=WATER_SUPPLY_OPTIONS,
        internet_options=INTERNET_OPTIONS,
    )


@app.route('/api/geocode')
def geocode_location():
    if not check_rate_limit('geocode_ip', client_ip(), 30, 60):
        return jsonify({'error': 'Too many location lookups. Please wait a moment.'}), 429
    query = (request.args.get('q') or '').strip()
    if not query or len(query) > 300:
        return jsonify({'error': 'Enter a street, landmark, neighbourhood, or Google Maps link.'}), 400

    # 1. Direct coordinates or Google Maps URL
    direct = extract_google_maps_coordinates(query)
    if direct:
        return jsonify({
            'latitude': direct[0],
            'longitude': direct[1],
            'label': f'Pinned coordinates ({direct[0]:.5f}, {direct[1]:.5f})',
            'source': 'coordinates',
        })

    # 2. Exact built-in Lusaka neighbourhood match
    needle = query.casefold()
    for name, coords in LUSAKA_NEIGHBOURHOOD_COORDS.items():
        if name.casefold() == needle or f'{name.casefold()}, lusaka' == needle:
            return jsonify({
                'latitude': coords[0],
                'longitude': coords[1],
                'label': f'{name}, Lusaka, Zambia',
                'compound': name,
                'source': 'neighbourhood',
            })

    # 3. Live OpenStreetMap Nominatim lookup biased to Lusaka, Zambia
    search_q = query if 'lusaka' in needle or 'zambia' in needle else f'{query}, Lusaka, Zambia'
    params = urllib.parse.urlencode({
        'q': search_q,
        'format': 'json',
        'limit': '1',
        'countrycodes': 'zm',
        'viewbox': '28.05,-15.62,28.62,-15.18',
    })
    url = f'https://nominatim.openstreetmap.org/search?{params}'
    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'KwachaStay/1.0 (+https://kwachastay.onrender.com)'},
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            results = json.loads(resp.read().decode('utf-8'))
        if results:
            lat = round(float(results[0]['lat']), 6)
            lng = round(float(results[0]['lon']), 6)
            label = results[0].get('display_name') or search_q
            return jsonify({
                'latitude': lat,
                'longitude': lng,
                'label': label,
                'source': 'nominatim',
            })
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError, OSError):
        pass

    # 4. Partial built-in Lusaka neighbourhood fallback
    for name, coords in LUSAKA_NEIGHBOURHOOD_COORDS.items():
        if needle in name.casefold() or name.casefold() in needle:
            return jsonify({
                'latitude': coords[0],
                'longitude': coords[1],
                'label': f'{name}, Lusaka, Zambia',
                'compound': name,
                'source': 'neighbourhood',
            })

    return jsonify({'error': 'Location not found. Try a Lusaka neighbourhood, road name, or drop a pin on the map.'}), 404

@app.route('/dashboard')
@login_required
def dashboard():
    return redirect(_home_dashboard_url(g.user))


@app.route('/tenant/dashboard')
@tenant_required
def tenant_dashboard():
    db = get_db()
    expire_pending_booking_requests(db, force=True)

    # 1. Fetch My Bookings (Tenant)
    bookings = db.execute('''
        SELECT b.*, p.title, p.compound, p.image_main,
               p.arrival_instructions, p.arrival_directions, p.nearby_essentials,
               p.emergency_contact_name, p.emergency_contact_phone,
               p.checkin_time, p.checkout_time, p.self_checkin_method,
               p.latitude AS property_latitude, p.longitude AS property_longitude
        FROM bookings b
        JOIN properties p ON b.property_id = p.id
        WHERE b.user_id = ?
        ORDER BY b.created_at DESC
    ''', (g.user['id'],)).fetchall()

    # 2. Fetch Saved Wishlist
    wishlist = db.execute('''
        SELECT p.*
        FROM wishlists w
        JOIN properties p ON w.property_id = p.id
        WHERE w.user_id = ?
        ORDER BY w.created_at DESC
    ''', (g.user['id'],)).fetchall()

    # 3. Fetch Messages
    messages = db.execute('''
        SELECT m.*, u.full_name as sender_name, p.title as property_title
        FROM messages m
        JOIN users u ON m.sender_id = u.id
        LEFT JOIN properties p ON m.property_id = p.id
        WHERE m.receiver_id = ?
        ORDER BY m.created_at DESC
    ''', (g.user['id'],)).fetchall()

    # 4. Fetch Saved Searches & Trip Plans
    saved_searches = db.execute(
        'SELECT * FROM saved_searches WHERE user_id = ? ORDER BY created_at DESC',
        (g.user['id'],)
    ).fetchall()
    trip_plans = db.execute(
        '''SELECT tp.*, COUNT(tpi.property_id) AS property_count
           FROM trip_plans tp
           LEFT JOIN trip_plan_items tpi ON tpi.trip_plan_id = tp.id
           WHERE tp.user_id = ?
           GROUP BY tp.id
           ORDER BY tp.created_at DESC''',
        (g.user['id'],),
    ).fetchall()

    return render_template(
        'tenant_dashboard.html',
        bookings=bookings,
        wishlist=wishlist,
        messages=messages,
        saved_searches=saved_searches,
        power_backup_options=POWER_BACKUP_OPTIONS,
        water_supply_options=WATER_SUPPLY_OPTIONS,
        trip_plans=trip_plans,
        mobile_money_enabled=flutterwave_checkout_enabled(),
        user=g.user,
    )


@app.route('/landlord/dashboard')
@landlord_required
def landlord_dashboard():
    db = get_db()
    expire_pending_booking_requests(db, force=True)

    # 1. Fetch My Listings (Landlord / Lister)
    properties = db.execute('''
        SELECT *, CAST(julianday('now') - julianday(last_confirmed_at) AS INTEGER)
            AS confirmation_age_days
        FROM properties WHERE owner_id = ? ORDER BY created_at DESC
    ''', (g.user['id'],)).fetchall()
    seasonal_pricing = {}
    calendar_imports = {}
    calendar_feed_urls = {}
    for prop in properties:
        seasonal_pricing[prop['id']] = db.execute(
            '''SELECT * FROM seasonal_pricing
               WHERE property_id = ? ORDER BY start_date''',
            (prop['id'],),
        ).fetchall()
        calendar_imports[prop['id']] = db.execute(
            '''SELECT ci.*, COUNT(cie.id) AS event_count
               FROM calendar_imports ci
               LEFT JOIN calendar_import_events cie ON cie.import_id = ci.id
               WHERE ci.property_id = ?
               GROUP BY ci.id ORDER BY ci.source_name''',
            (prop['id'],),
        ).fetchall()
        feed_token = session.pop(f'calendar_feed_{prop["id"]}', None)
        if feed_token:
            calendar_feed_urls[prop['id']] = url_for(
                'public_calendar_feed', token=feed_token, _external=True
            )
    photo_checklists = {}
    listing_quality = {}
    host_reminders = {}
    for prop in properties:
        uploaded_categories = {
            row['category'] for row in db.execute(
                'SELECT category FROM property_images WHERE property_id = ?',
                (prop['id'],),
            ).fetchall()
            if row['category']
        }
        if prop['image_main']:
            uploaded_categories.add(prop['main_photo_category'] or 'other')
        photo_checklists[prop['id']] = uploaded_categories
        quality_checks = [
            (bool(prop['description'] and len(prop['description'].strip()) >= 120),
             'Add a fuller description (at least 120 characters).'),
            (len(uploaded_categories & {'bedroom', 'bathroom', 'kitchen', 'entrance', 'parking'}) >= 3,
             'Add photos of at least three key areas.'),
            (prop['latitude'] is not None and prop['longitude'] is not None,
             'Pin the listing location on the map.'),
            (bool(prop['power_backup'] and prop['water_supply'] and prop['internet_availability']),
             'Complete the power, water, and internet details.'),
            (bool(prop['arrival_instructions']),
             'Add check-in instructions for confirmed guests.'),
            (bool(prop['has_wifi'] or prop['has_solar'] or prop['has_borehole']
                  or prop['has_parking'] or prop['has_ac'] or prop['has_pool']),
             'Select the amenities guests can expect.'),
        ]
        listing_quality[prop['id']] = {
            'score': sum(1 for complete, _ in quality_checks if complete),
            'tips': [tip for complete, tip in quality_checks if not complete],
        }
        reminders = list(listing_quality[prop['id']]['tips'])
        if not prop['last_confirmed_at'] or (prop['confirmation_age_days'] is not None
                                              and prop['confirmation_age_days'] > 30):
            reminders.insert(0, 'Confirm price, dates, and listing details; it has been more than 30 days.')
        host_reminders[prop['id']] = reminders

    host_analytics = {
        'views': sum(prop['view_count'] or 0 for prop in properties),
        'inquiries': 0,
        'confirmed_bookings': 0,
        'conversion_percent': None,
        'response_stats': get_host_response_stats(db, g.user['id']),
        'suggestions': [],
    }
    if properties:
        host_analytics['inquiries'] = db.execute(
            '''SELECT COUNT(*)
               FROM messages m
               JOIN properties p ON p.id = m.property_id
               WHERE p.owner_id = ? AND m.receiver_id = ?
                 AND m.sender_id != ? AND m.parent_id IS NULL''',
            (g.user['id'], g.user['id'], g.user['id']),
        ).fetchone()[0]
        host_analytics['confirmed_bookings'] = db.execute(
            '''SELECT COUNT(*)
               FROM bookings b
               JOIN properties p ON p.id = b.property_id
               WHERE p.owner_id = ? AND b.booking_status = 'confirmed' ''',
            (g.user['id'],),
        ).fetchone()[0]
        if host_analytics['views']:
            host_analytics['conversion_percent'] = round(
                host_analytics['confirmed_bookings'] * 100 / host_analytics['views'], 1
            )

    if not properties:
        host_analytics['suggestions'].append('Add your first listing to start tracking its performance.')
    else:
        incomplete_listings = sum(
            1 for prop in properties if listing_quality[prop['id']]['tips']
        )
        if incomplete_listings:
            host_analytics['suggestions'].append(
                f'Complete photos, location, and property details on {incomplete_listings} listing'
                f'{"s" if incomplete_listings != 1 else ""} to build guest confidence.'
            )
        if host_analytics['views'] >= 20 and not host_analytics['inquiries']:
            host_analytics['suggestions'].append(
                'Your listings have views but no enquiries yet. Review photos, pricing, and availability.'
            )
        response_stats = host_analytics['response_stats']
        if response_stats and response_stats['reply_rate_percent'] < 70:
            host_analytics['suggestions'].append(
                'Reply to new guest enquiries promptly to improve your response rate.'
            )
        if (host_analytics['views'] >= 50 and host_analytics['conversion_percent'] is not None
                and host_analytics['conversion_percent'] < 2):
            host_analytics['suggestions'].append(
                'Review your prices and calendar accuracy to help turn listing visits into bookings.'
            )
        if not host_analytics['suggestions']:
            host_analytics['suggestions'].append(
                'Your listings look up to date. Keep availability and guest replies current.'
            )

    # 2. Fetch Incoming Bookings (for landlord properties)
    incoming_bookings = []
    earnings = {'total': 0, 'confirmed': 0, 'pending': 0, 'count': 0, 'recent': []}
    if properties:
        placeholders = ','.join('?' for _ in properties)
        property_ids = [p['id'] for p in properties]

        query = f'''
            SELECT b.*, p.title, u.email as tenant_email,
                   u.email_verified_at AS tenant_email_verified_at,
                   u.phone_verified_at AS tenant_phone_verified_at,
                   (SELECT COUNT(*) FROM bookings completed
                    WHERE completed.user_id = b.user_id
                      AND completed.booking_status = 'confirmed'
                      AND completed.check_out <= date('now')) AS guest_completed_stays,
                   (SELECT COUNT(*) FROM bookings cancelled
                    WHERE cancelled.user_id = b.user_id
                      AND cancelled.booking_status = 'cancelled') AS guest_cancellations
            FROM bookings b
            JOIN properties p ON b.property_id = p.id
            LEFT JOIN users u ON b.user_id = u.id
            WHERE p.id IN ({placeholders})
            ORDER BY b.created_at DESC
        '''
        incoming_bookings = [
            dict(row) for row in db.execute(query, property_ids).fetchall()
        ]

        for b in incoming_bookings:
            if b['booking_status'] == 'confirmed' and b['payment_status'] == 'paid':
                earnings['confirmed'] += b['total_price'] or 0
                earnings['count'] += 1
            elif b['booking_status'] == 'pending':
                earnings['pending'] += b['total_price'] or 0
        earnings['total'] = earnings['confirmed'] + earnings['pending']
        earnings['recent'] = incoming_bookings[:5]
        refresh_payout_ledger(db, g.user['id'])
        db.commit()
        payout_ledger = db.execute(
            '''SELECT pl.*, p.title, b.check_in, b.check_out, b.tx_ref
               FROM payout_ledger pl
               JOIN bookings b ON b.id = pl.booking_id
               JOIN properties p ON p.id = b.property_id
               WHERE pl.owner_id = ?
               ORDER BY pl.created_at DESC''',
            (g.user['id'],),
        ).fetchall()
    else:
        payout_ledger = []

    # 3. Fetch Messages
    messages = db.execute('''
        SELECT m.*, u.full_name as sender_name, p.title as property_title
        FROM messages m
        JOIN users u ON m.sender_id = u.id
        LEFT JOIN properties p ON m.property_id = p.id
        WHERE m.receiver_id = ?
        ORDER BY m.created_at DESC
    ''', (g.user['id'],)).fetchall()

    # 4. Fetch Payout Methods
    payout_methods = db.execute(
        'SELECT * FROM payout_methods WHERE user_id = ? ORDER BY is_primary DESC',
        (g.user['id'],)
    ).fetchall()

    return render_template(
        'landlord_dashboard.html',
        properties=properties,
        incoming_bookings=incoming_bookings,
        messages=messages,
        earnings=earnings,
        payout_methods=payout_methods,
        host_analytics=host_analytics,
        seasonal_pricing=seasonal_pricing,
        calendar_imports=calendar_imports,
        calendar_feed_urls=calendar_feed_urls,
        payout_ledger=payout_ledger,
        photo_checklists=photo_checklists,
        listing_quality=listing_quality,
        host_reminders=host_reminders,
        user=g.user,
    )

@app.route('/property/<int:property_id>')
def property_details(property_id):
    db = get_db()

    # Increment view count (only for non-owners and non-repeated views in session)
    viewed_key = f'viewed_{property_id}'
    if g.user is None or True:  # count all unique-session views
        if viewed_key not in session:
            db.execute('UPDATE properties SET view_count = COALESCE(view_count, 0) + 1 WHERE id = ?', (property_id,))
            db.commit()
            session[viewed_key] = True

    # Fetch Property + Owner Info
    property = db.execute('''
        SELECT p.*, u.full_name as owner_name, u.profile_pic as owner_pic,
               CASE WHEN p.last_confirmed_at IS NOT NULL
                    AND julianday('now') - julianday(p.last_confirmed_at) <= 30
                    THEN 1 ELSE 0 END AS listing_recently_confirmed,
               u.created_at as owner_joined, u.host_verification_status as owner_verification_status,
               u.email_verified_at as owner_email_verified_at
        FROM properties p
        JOIN users u ON p.owner_id = u.id
        WHERE p.id = ?
    ''', (property_id,)).fetchone()
    
    if property is None:
        flash('Property not found.', 'error')
        return redirect(url_for('index'))
    if not property['is_active'] and (
        not g.user or (g.user['id'] != property['owner_id'] and not g.user['is_admin'])
    ):
        flash('Property not found.', 'error')
        return redirect(url_for('index'))

    # Fetch Images (always include image_main first, skip missing local uploads on Supabase)
    def _usable_image_url(url):
        if not url:
            return False
        if url.startswith('/static/uploads/'):
            local_file = os.path.join(BASE_DIR, url.lstrip('/').replace('/', os.sep))
            return os.path.isfile(local_file)
        return True

    images = db.execute(
        'SELECT image_url, category FROM property_images WHERE property_id = ?',
        (property_id,),
    ).fetchall()
    extra_urls = [img['image_url'] for img in images if _usable_image_url(img['image_url'])]
    image_list = []
    if _usable_image_url(property['image_main']):
        image_list.append(property['image_main'])
    for url in extra_urls:
        if url not in image_list:
            image_list.append(url)
    photo_categories = {img['category'] for img in images if img['category']}
    if property['image_main']:
        photo_categories.add(property['main_photo_category'] or 'other')
    
    # Fetch Reviews
    review_rows = db.execute('''
        SELECT r.*, u.full_name as reviewer_name 
        FROM reviews r
        JOIN users u ON r.user_id = u.id
        WHERE r.property_id = ?
        ORDER BY r.created_at DESC
    ''', (property_id,)).fetchall()
    review_photo_rows = db.execute(
        '''SELECT rp.review_id, rp.image_url
           FROM review_photos rp
           JOIN reviews r ON r.id = rp.review_id
           WHERE r.property_id = ?
           ORDER BY rp.id''',
        (property_id,),
    ).fetchall()
    photos_by_review = {}
    for photo in review_photo_rows:
        photos_by_review.setdefault(photo['review_id'], []).append(photo['image_url'])
    reviews = [
        dict(review, photos=photos_by_review.get(review['id'], []))
        for review in review_rows
    ]
    review_averages = db.execute(
        '''SELECT AVG(cleanliness_rating) AS cleanliness,
                  AVG(accuracy_rating) AS accuracy,
                  AVG(communication_rating) AS communication,
                  AVG(location_rating) AS location
           FROM reviews WHERE property_id = ?''',
        (property_id,),
    ).fetchone()
    
    # Check if wishlisted
    is_wishlisted = False
    has_booking = False
    has_review = False
    if g.user:
        check = db.execute('SELECT id FROM wishlists WHERE user_id = ? AND property_id = ?',
                           (g.user['id'], property_id)).fetchone()
        if check:
            is_wishlisted = True
        # Review gate: only users with a paid or confirmed booking can review
        booking_check = db.execute('''
            SELECT id FROM bookings
            WHERE user_id = ? AND property_id = ?
            AND booking_status = 'confirmed'
              AND check_out <= ?
        ''', (g.user['id'], property_id, date.today().isoformat())).fetchone()
        if booking_check:
            has_booking = True
            reviewed = db.execute(
                'SELECT id FROM reviews WHERE user_id = ? AND property_id = ?',
                (g.user['id'], property_id),
            ).fetchone()
            has_review = bool(reviewed)

    # Fetch similar properties (same compound, excluding current)
    similar_raw = db.execute('''
        SELECT p.*, u.full_name as owner_name,
               (SELECT AVG(r.rating) FROM reviews r WHERE r.property_id = p.id) as avg_rating,
               (SELECT COUNT(r.id) FROM reviews r WHERE r.property_id = p.id) as review_count
        FROM properties p
        JOIN users u ON p.owner_id = u.id
        WHERE p.is_active = 1 AND p.compound = ? AND p.id != ?
        ORDER BY p.created_at DESC
        LIMIT 3
    ''', (property['compound'], property_id)).fetchall()

    similar = []
    for s in similar_raw:
        s_dict = dict(s)
        imgs = db.execute('SELECT image_url FROM property_images WHERE property_id = ?', (s['id'],)).fetchall()
        s_dict['images'] = [i['image_url'] for i in imgs]
        if not s_dict['images'] and s['image_main']:
            s_dict['images'] = [s['image_main']]
        s_dict['rating'] = round(s['avg_rating'], 1) if s['avg_rating'] else None
        similar.append(s_dict)

    has_exact_pin = property['latitude'] is not None and property['longitude'] is not None
    if has_exact_pin:
        map_lat = float(property['latitude'])
        map_lng = float(property['longitude'])
    else:
        map_lat, map_lng = get_neighbourhood_coordinates(property['compound'])

    return render_template('property_details.html',
                           property=property,
                           has_exact_pin=has_exact_pin,
                           map_lat=map_lat,
                           map_lng=map_lng,
                           effective_hourly_rate=get_effective_hourly_rate(property),
                           can_book_hourly=supports_hourly_booking(property),
                           upfront_months=get_upfront_months(property),
                           room_sharing_options=ROOM_SHARING_OPTIONS,
                           images=image_list,
                           photo_categories=photo_categories,
                           reviews=reviews,
                           review_averages=review_averages,
                           is_wishlisted=is_wishlisted,
                           has_booking=has_booking,
                           has_review=has_review,
                           host_response_stats=get_host_response_stats(db, property['owner_id']),
                           host_reliability_stats=get_host_reliability_stats(db, property['owner_id']),
                           power_backup_options=POWER_BACKUP_OPTIONS,
                           water_supply_options=WATER_SUPPLY_OPTIONS,
                           internet_options=INTERNET_OPTIONS,
                           similar=similar)


@app.route('/property/<int:property_id>/confirm-details', methods=['POST'])
@landlord_required
def confirm_listing_details(property_id):
    db = get_db()
    try:
        db.execute('BEGIN IMMEDIATE')
        result = db.execute(
            '''UPDATE properties SET last_confirmed_at = CURRENT_TIMESTAMP
               WHERE id = ? AND owner_id = ?''',
            (property_id, g.user['id']),
        )
        if result.rowcount != 1:
            db.rollback()
            flash('Listing not found or you are not its host.', 'error')
            return redirect(url_for('dashboard'))
        db.commit()
        flash('Listing details and availability confirmed as current.', 'success')
    except DB_ERRORS:
        db.rollback()
        app.logger.exception('Could not confirm listing details for property %s', property_id)
        flash('Could not confirm the listing. Please try again.', 'error')
    return redirect(url_for('dashboard'))

@app.route('/add_review/<int:property_id>', methods=['POST'])
@tenant_required
def add_review(property_id):
    rating = request.form.get('rating')
    comment = request.form.get('comment')
    review_photos = [
        photo for photo in request.files.getlist('photos')
        if photo and photo.filename
    ]
    if len(review_photos) > 3:
        flash('You can add up to 3 photos to a review.', 'error')
        return redirect(url_for('property_details', property_id=property_id))
    validated_review_photos = []
    for photo in review_photos:
        try:
            canonical_ext, canonical_mime = validate_image_upload(photo)
        except ValueError as error:
            flash(str(error), 'error')
            return redirect(url_for('property_details', property_id=property_id))
        validated_review_photos.append((photo, canonical_ext, canonical_mime))

    category_fields = {
        'cleanliness_rating': 'Cleanliness',
        'accuracy_rating': 'Accuracy',
        'communication_rating': 'Communication',
        'location_rating': 'Location',
    }
    try:
        rating_value = int(rating)
        category_ratings = {
            field: int(request.form.get(field, ''))
            for field in category_fields
        }
    except (TypeError, ValueError):
        flash('Give an overall score and a score for every review category.', 'error')
        return redirect(url_for('property_details', property_id=property_id))
    if not 1 <= rating_value <= 5 or any(not 1 <= value <= 5 for value in category_ratings.values()):
        flash('Ratings must be between 1 and 5 stars.', 'error')
        return redirect(url_for('property_details', property_id=property_id))

    db = get_db()

    # Review gate: must have a paid or confirmed booking
    booking_check = db.execute('''
        SELECT id FROM bookings
        WHERE user_id = ? AND property_id = ?
        AND booking_status = \'confirmed\'
          AND check_out <= ?
    ''', (g.user['id'], property_id, date.today().isoformat())).fetchone()

    if not booking_check:
        flash('You can only review a property after a confirmed stay.', 'error')
        return redirect(url_for('property_details', property_id=property_id))

    # Prevent duplicate review
    existing = db.execute('SELECT id FROM reviews WHERE user_id = ? AND property_id = ?',
                          (g.user['id'], property_id)).fetchone()
    if existing:
        flash('You have already reviewed this property.', 'info')
        return redirect(url_for('property_details', property_id=property_id))

    saved_photo_paths = []
    if review_photos and not app.config['UPLOADS_ENABLED']:
        flash('Photo uploads are disabled until durable production storage is configured.', 'error')
        return redirect(url_for('property_details', property_id=property_id))
    try:
        for photo, canonical_ext, canonical_mime in validated_review_photos:
            filename = f'{uuid.uuid4().hex}.{canonical_ext}'
            save_path = upload_storage.save(photo, filename, content_type=canonical_mime)
            image_url = (
                save_path if STORAGE_BACKEND == 'supabase'
                else url_for('static', filename=f'uploads/{filename}')
            )
            saved_photo_paths.append((save_path, image_url))

        review_cursor = db.execute(
            '''INSERT INTO reviews (
                property_id, user_id, rating, cleanliness_rating, accuracy_rating,
                communication_rating, location_rating, comment
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            (
                property_id, g.user['id'], rating_value,
                category_ratings['cleanliness_rating'], category_ratings['accuracy_rating'],
                category_ratings['communication_rating'], category_ratings['location_rating'],
                (comment or '').strip()[:2000],
            ),
        )
        db.executemany(
            'INSERT INTO review_photos (review_id, image_url) VALUES (?, ?)',
            [(review_cursor.lastrowid, image_url) for _, image_url in saved_photo_paths],
        )
        db.commit()
    except (OSError,) + DB_ERRORS:
        db.rollback()
        for save_path, _ in saved_photo_paths:
            try:
                upload_storage.delete(save_path)
            except FileNotFoundError:
                pass
        app.logger.exception('Could not save verified-stay review for property %s', property_id)
        flash('Could not post your review. Please try again.', 'error')
        return redirect(url_for('property_details', property_id=property_id))

    flash('Review posted successfully!', 'success')
    return redirect(url_for('property_details', property_id=property_id))

@app.route('/toggle_wishlist/<int:property_id>', methods=['POST'])
@tenant_required
def toggle_wishlist(property_id):
    db = get_db()
    existing = db.execute('SELECT * FROM wishlists WHERE user_id = ? AND property_id = ?', 
                          (g.user['id'], property_id)).fetchone()
    
    if existing:
        db.execute('DELETE FROM wishlists WHERE user_id = ? AND property_id = ?', 
                   (g.user['id'], property_id))
        action = 'removed'
    else:
        db.execute('INSERT INTO wishlists (user_id, property_id) VALUES (?, ?)', 
                   (g.user['id'], property_id))
        action = 'added'
    
    db.commit()
    return {'status': 'success', 'action': action}


# --- Booking Cancellation by Tenant ---
@app.route('/booking/cancel/<int:booking_id>', methods=['POST'])
@tenant_required
def cancel_booking(booking_id):
    db = get_db()
    booking = db.execute('''
        SELECT b.*, p.title, p.owner_id, u.email as owner_email, u.full_name as owner_fullname
        FROM bookings b
        JOIN properties p ON b.property_id = p.id
        LEFT JOIN users u ON p.owner_id = u.id
        WHERE b.id = ? AND b.user_id = ?
    ''', (booking_id, g.user['id'])).fetchone()

    if not booking:
        flash('Booking not found or unauthorized.', 'error')
        return redirect(url_for('dashboard'))

    if booking['booking_status'] in ('declined', 'cancelled'):
        flash('This booking cannot be cancelled.', 'error')
        return redirect(url_for('dashboard'))

    if booking['check_in'] <= date.today().isoformat():
        flash('A stay cannot be cancelled on or after its check-in date. Contact support for help.', 'error')
        return redirect(url_for('dashboard'))

    open_refund_request = (
        booking['payment_status'] == 'paid'
        and booking['refund_status'] not in ('requested', 'refunded')
    )
    refund_update = ", refund_status = 'requested'" if open_refund_request else ''
    db.execute(
        f"UPDATE bookings SET booking_status = 'cancelled'{refund_update} WHERE id = ?",
        (booking_id,),
    )
    db.commit()

    # Notify the host
    try:
        create_notification(db, booking['owner_id'],
            f"Booking for '{booking['title']}' was cancelled by {g.user['full_name']}.",
            url_for('dashboard'))
        db.commit()
    except Exception:
        app.logger.error('Could not create booking cancellation notification for booking %s.', booking_id)

    if booking['payment_status'] == 'paid' and booking['refund_status'] == 'requested':
        flash('Booking cancelled. Your existing refund request remains under review.', 'info')
    elif open_refund_request:
        flash('Booking cancelled. A refund request was opened for review under the listing policy.', 'info')
    else:
        flash('Booking cancelled successfully.', 'info')
    return redirect(url_for('dashboard'))


# --- Delete Property ---
@app.route('/property/<int:property_id>/delete', methods=['POST'])
@landlord_required
def delete_property(property_id):
    db = get_db()
    prop = db.execute('SELECT * FROM properties WHERE id = ? AND owner_id = ?',
                      (property_id, g.user['id'])).fetchone()
    if not prop:
        flash('Property not found or unauthorized.', 'error')
        return redirect(url_for('dashboard'))

    # Safety: block deletion if there are pending/confirmed bookings
    active = db.execute("""
        SELECT id FROM bookings
        WHERE property_id = ? AND booking_status IN ('pending', 'confirmed')
    """, (property_id,)).fetchone()
    if active:
        flash('Cannot delete a property with active bookings. Please decline or wait for them to complete first.', 'error')
        return redirect(url_for('dashboard'))

    # Delete associated data
    db.execute('DELETE FROM property_images WHERE property_id = ?', (property_id,))
    db.execute('DELETE FROM wishlists WHERE property_id = ?', (property_id,))
    db.execute('DELETE FROM availability WHERE property_id = ?', (property_id,))
    db.execute('DELETE FROM reviews WHERE property_id = ?', (property_id,))
    db.execute('DELETE FROM properties WHERE id = ? AND owner_id = ?', (property_id, g.user['id']))
    db.commit()
    flash('Property permanently deleted.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/delist_property/<int:property_id>', methods=['POST'])
@landlord_required
def delist_property(property_id):
    db = get_db()
    db.execute('UPDATE properties SET is_active = 0 WHERE id = ? AND owner_id = ?', 
               (property_id, g.user['id']))
    db.commit()
    flash('Property delisted successfully.', 'info')
    return redirect(url_for('dashboard'))

@app.route('/relist_property/<int:property_id>', methods=['POST'])
@landlord_required
def relist_property(property_id):
    db = get_db()
    cursor = db.execute(
        'UPDATE properties SET is_active = 1 WHERE id = ? AND owner_id = ? AND is_active = 0',
        (property_id, g.user['id']),
    )
    if cursor.rowcount:
        property_row = db.execute(
            'SELECT * FROM properties WHERE id = ?', (property_id,)
        ).fetchone()
        notify_matching_searches(db, property_row, event='available')
    db.commit()
    flash('Property relisted successfully.', 'success')
    return redirect(url_for('dashboard'))

# --- Availability ---
@app.route('/block_date/<int:property_id>', methods=['POST'])
@landlord_required
def block_date(property_id):
    blocked_date = parse_iso_date(request.form.get('date'))
    db = get_db()
    check = db.execute('SELECT id FROM properties WHERE id = ? AND owner_id = ?',
                       (property_id, g.user['id'])).fetchone()
    if not check:
        flash('Unauthorized.', 'error')
        return redirect(url_for('dashboard'))
    if not blocked_date or blocked_date < date.today():
        flash('Choose a valid future date to block.', 'error')
        return redirect(url_for('dashboard'))

    try:
        db.execute('BEGIN IMMEDIATE')
        occupied = db.execute(
            '''SELECT id FROM bookings
               WHERE property_id = ? AND booking_status IN ('pending', 'confirmed')
                 AND check_in <= ? AND check_out > ? LIMIT 1''',
            (property_id, blocked_date.isoformat(), blocked_date.isoformat()),
        ).fetchone()
        if occupied:
            db.rollback()
            flash('That date is included in an existing booking request or confirmed stay.', 'error')
            return redirect(url_for('dashboard'))
        db.execute('INSERT INTO availability (property_id, date, status) VALUES (?, ?, ?)',
                   (property_id, blocked_date.isoformat(), 'blocked'))
        db.commit()
        flash('Date blocked.', 'success')
    except DB_INTEGRITY_ERRORS:
        db.rollback()
        flash('Date already blocked.', 'info')
    except DB_ERRORS:
        db.rollback()
        app.logger.exception('Could not block date %s for property %s', blocked_date, property_id)
        flash('Could not block that date. Please try again.', 'error')
        
    return redirect(url_for('dashboard')) # Ideally AJAX


@app.route('/property/<int:property_id>/availability')
def property_availability(property_id):
    month_value = request.args.get('month', '')
    try:
        month_start = date.fromisoformat(f'{month_value}-01')
    except ValueError:
        return jsonify({'error': 'Use a month in YYYY-MM format.'}), 400
    month_end = add_months(month_start, 1)

    db = get_db()
    property_row = db.execute(
        'SELECT id, owner_id, is_active FROM properties WHERE id = ?',
        (property_id,),
    ).fetchone()
    if not property_row or (not property_row['is_active'] and
                            (not g.user or (g.user['id'] != property_row['owner_id'] and not g.user['is_admin']))):
        return jsonify({'error': 'Property not found.'}), 404

    statuses = {}
    blocked_dates = db.execute(
        '''SELECT date FROM availability
           WHERE property_id = ? AND status = 'blocked'
             AND date >= ? AND date < ?''',
        (property_id, month_start.isoformat(), month_end.isoformat()),
    ).fetchall()
    for row in blocked_dates:
        statuses[row['date']] = 'blocked'

    imported_dates = db.execute(
        '''SELECT cie.start_date, cie.end_date
           FROM calendar_import_events cie
           JOIN calendar_imports ci ON ci.id = cie.import_id
           WHERE ci.property_id = ? AND cie.start_date < ? AND cie.end_date > ?''',
        (property_id, month_end.isoformat(), month_start.isoformat()),
    ).fetchall()
    for row in imported_dates:
        start = max(parse_iso_date(row['start_date']), month_start)
        end = min(parse_iso_date(row['end_date']), month_end)
        current = start
        while current < end:
            statuses.setdefault(current.isoformat(), 'blocked')
            current += timedelta(days=1)

    bookings = db.execute(
        '''SELECT check_in, check_out, booking_status FROM bookings
           WHERE property_id = ? AND booking_status IN ('pending', 'confirmed')
             AND check_in < ? AND check_out > ?''',
        (property_id, month_end.isoformat(), month_start.isoformat()),
    ).fetchall()
    for booking in bookings:
        start = max(parse_iso_date(booking['check_in']), month_start)
        end = min(parse_iso_date(booking['check_out']), month_end)
        current = start
        booking_status = 'confirmed' if booking['booking_status'] == 'confirmed' else 'pending'
        while current < end:
            statuses[current.isoformat()] = booking_status
            current += timedelta(days=1)

    return jsonify({
        'month': month_start.strftime('%Y-%m'),
        'dates': statuses,
    })


def ical_escape(value):
    return str(value or '').replace('\\', '\\\\').replace(';', '\\;').replace(',', '\\,').replace('\r\n', '\\n').replace('\n', '\\n')


def parse_ical_events(contents):
    if len(contents) > 1024 * 1024:
        raise ValueError('Calendar file must be smaller than 1 MB.')
    try:
        text = contents.decode('utf-8-sig')
    except UnicodeDecodeError as error:
        raise ValueError('Calendar file must use UTF-8 text encoding.') from error

    unfolded = re.sub(r'\r?\n[ \t]', '', text).splitlines()
    events = []
    current = None
    for line in unfolded:
        if line.strip().upper() == 'BEGIN:VEVENT':
            if current is not None:
                raise ValueError('Calendar file contains an incomplete event.')
            current = {}
        elif line.strip().upper() == 'END:VEVENT':
            if current is None:
                continue
            start_value = current.get('DTSTART')
            end_value = current.get('DTEND')
            if current.get('STATUS', '').upper() != 'CANCELLED' and start_value:
                if not re.fullmatch(r'\d{8}', start_value):
                    raise ValueError('Only all-day calendar dates are supported for imported stays.')
                start = datetime.strptime(start_value, '%Y%m%d').date()
                if end_value and not re.fullmatch(r'\d{8}', end_value):
                    raise ValueError('Imported calendar end dates must use all-day dates.')
                end = datetime.strptime(end_value, '%Y%m%d').date() if end_value else start + timedelta(days=1)
                if end <= start or (end - start).days > 366:
                    raise ValueError('Each imported calendar event must cover 1 to 366 days.')
                uid = current.get('UID') or hashlib.sha256(
                    f'{start.isoformat()}:{end.isoformat()}'.encode('ascii')
                ).hexdigest()
                if len(uid) > 255:
                    raise ValueError('Calendar event identifier is too long.')
                events.append((uid, start.isoformat(), end.isoformat()))
                if len(events) > 1000:
                    raise ValueError('Calendar file contains more than 1,000 events.')
            current = None
        elif current is not None and ':' in line:
            name, value = line.split(':', 1)
            property_name = name.split(';', 1)[0].upper()
            if property_name in ('UID', 'DTSTART', 'DTEND', 'STATUS'):
                current[property_name] = value.strip()
    if current is not None:
        raise ValueError('Calendar file contains an incomplete event.')
    if not events:
        raise ValueError('No valid all-day stays were found in this calendar file.')
    return events


def issue_calendar_feed(db, property_id, owner_id):
    token = secrets.token_urlsafe(32)
    db.execute(
        '''INSERT INTO calendar_feeds (property_id, owner_id, token_hash)
           VALUES (?, ?, ?)
           ON CONFLICT(property_id) DO UPDATE SET
               owner_id = excluded.owner_id,
               token_hash = excluded.token_hash,
               created_at = CURRENT_TIMESTAMP''',
        (property_id, owner_id, hashlib.sha256(token.encode('utf-8')).hexdigest()),
    )
    return token


def render_calendar_response(property_row, events):
    now = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    lines = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//KwachaStay//Availability Calendar//EN',
        'CALSCALE:GREGORIAN',
        'METHOD:PUBLISH',
        f'X-WR-CALNAME:{ical_escape(property_row["title"])} availability',
    ]
    for start, end, summary, status in sorted(events, key=lambda event: (event[0], event[1])):
        uid = f'{property_row["id"]}-{start.strftime("%Y%m%d")}-{end.strftime("%Y%m%d")}-{status}@kwachastay'
        lines.extend([
            'BEGIN:VEVENT',
            f'UID:{uid}',
            f'DTSTAMP:{now}',
            f'DTSTART;VALUE=DATE:{start.strftime("%Y%m%d")}',
            f'DTEND;VALUE=DATE:{end.strftime("%Y%m%d")}',
            f'SUMMARY:{ical_escape(summary)}',
            f'STATUS:{status}',
            'END:VEVENT',
        ])
    lines.append('END:VCALENDAR')
    return Response(
        '\r\n'.join(lines) + '\r\n',
        mimetype='text/calendar',
        headers={'Content-Disposition': f'attachment; filename="kwachastay-{property_row["id"]}.ics"'},
    )


@app.route('/property/<int:property_id>/calendar.ics')
@landlord_required
def export_property_calendar(property_id):
    db = get_db()
    property_row = db.execute(
        'SELECT id, owner_id, title FROM properties WHERE id = ? AND owner_id = ?',
        (property_id, g.user['id']),
    ).fetchone()
    if not property_row:
        flash('Listing not found or unauthorized.', 'error')
        return redirect(url_for('dashboard'))

    events = []
    bookings = db.execute(
        '''SELECT check_in, check_out, booking_status FROM bookings
           WHERE property_id = ? AND booking_status IN ('pending', 'confirmed')
           ORDER BY check_in''',
        (property_id,),
    ).fetchall()
    for booking in bookings:
        start = parse_iso_date(booking['check_in'])
        end = parse_iso_date(booking['check_out'])
        if not start or not end or end <= start:
            app.logger.warning('Skipping invalid booking dates in calendar export for property %s', property_id)
            continue
        summary = 'Tentative booking' if booking['booking_status'] == 'pending' else 'Booked'
        events.append((start, end, summary, 'CONFIRMED' if summary == 'Booked' else 'TENTATIVE'))

    blocked_dates = db.execute(
        '''SELECT date FROM availability
           WHERE property_id = ? AND status = 'blocked'
           ORDER BY date''',
        (property_id,),
    ).fetchall()
    for row in blocked_dates:
        start = parse_iso_date(row['date'])
        if start:
            events.append((start, start + timedelta(days=1), 'Unavailable', 'CONFIRMED'))

    imported_dates = db.execute(
        '''SELECT cie.start_date, cie.end_date
           FROM calendar_import_events cie
           JOIN calendar_imports ci ON ci.id = cie.import_id
           WHERE ci.property_id = ?''',
        (property_id,),
    ).fetchall()
    for row in imported_dates:
        start, end = parse_iso_date(row['start_date']), parse_iso_date(row['end_date'])
        if start and end and end > start:
            events.append((start, end, 'Unavailable', 'CONFIRMED'))
    return render_calendar_response(property_row, events)


@app.route('/calendar/feed/<token>.ics')
def public_calendar_feed(token):
    token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
    db = get_db()
    property_row = db.execute(
        '''SELECT p.id, p.title FROM calendar_feeds cf
           JOIN properties p ON p.id = cf.property_id
           WHERE cf.token_hash = ? AND p.is_active = 1''',
        (token_hash,),
    ).fetchone()
    if not property_row:
        return Response('Calendar feed not found.', status=404, mimetype='text/plain')

    events = []
    bookings = db.execute(
        '''SELECT check_in, check_out FROM bookings
           WHERE property_id = ? AND booking_status = 'confirmed'
             AND check_out >= date('now') ORDER BY check_in''',
        (property_row['id'],),
    ).fetchall()
    for booking in bookings:
        start, end = parse_iso_date(booking['check_in']), parse_iso_date(booking['check_out'])
        if start and end and end > start:
            events.append((start, end, 'Unavailable', 'CONFIRMED'))
    blocked_dates = db.execute(
        '''SELECT date FROM availability
           WHERE property_id = ? AND status = 'blocked' AND date >= date('now')''',
        (property_row['id'],),
    ).fetchall()
    for row in blocked_dates:
        start = parse_iso_date(row['date'])
        if start:
            events.append((start, start + timedelta(days=1), 'Unavailable', 'CONFIRMED'))
    imported_dates = db.execute(
        '''SELECT cie.start_date, cie.end_date
           FROM calendar_import_events cie
           JOIN calendar_imports ci ON ci.id = cie.import_id
           WHERE ci.property_id = ? AND cie.end_date >= date('now')''',
        (property_row['id'],),
    ).fetchall()
    for row in imported_dates:
        start, end = parse_iso_date(row['start_date']), parse_iso_date(row['end_date'])
        if start and end and end > start:
            events.append((start, end, 'Unavailable', 'CONFIRMED'))
    return render_calendar_response(property_row, events)


@app.route('/calendar/<int:property_id>/feed', methods=['POST'])
@landlord_required
def create_calendar_feed(property_id):
    db = get_db()
    if not db.execute(
        'SELECT id FROM properties WHERE id = ? AND owner_id = ?',
        (property_id, g.user['id']),
    ).fetchone():
        flash('Listing not found or unauthorized.', 'error')
        return redirect(url_for('dashboard'))
    token = issue_calendar_feed(db, property_id, g.user['id'])
    db.commit()
    session[f'calendar_feed_{property_id}'] = token
    flash('A private calendar subscription link was generated. Generate a new link to revoke this one.', 'success')
    return redirect(url_for('dashboard'))


@app.route('/calendar/<int:property_id>/import', methods=['POST'])
@landlord_required
def import_property_calendar(property_id):
    db = get_db()
    if not db.execute(
        'SELECT id FROM properties WHERE id = ? AND owner_id = ?',
        (property_id, g.user['id']),
    ).fetchone():
        flash('Listing not found or unauthorized.', 'error')
        return redirect(url_for('dashboard'))
    uploaded = request.files.get('calendar_file')
    if not uploaded or not uploaded.filename or not uploaded.filename.lower().endswith('.ics'):
        flash('Choose a valid .ics calendar export to import.', 'error')
        return redirect(url_for('dashboard'))
    source_name = re.sub(r'[^A-Za-z0-9._ -]', '', uploaded.filename.rsplit('.', 1)[0]).strip()[:60]
    source_name = source_name or 'Imported calendar'
    try:
        events = parse_ical_events(uploaded.stream.read(1024 * 1024 + 1))
    except ValueError as error:
        flash(str(error), 'error')
        return redirect(url_for('dashboard'))
    try:
        db.execute('BEGIN IMMEDIATE')
        db.execute(
            '''INSERT INTO calendar_imports (property_id, source_name)
               VALUES (?, ?)
               ON CONFLICT(property_id, source_name) DO UPDATE SET
                   imported_at = CURRENT_TIMESTAMP''',
            (property_id, source_name),
        )
        import_id = db.execute(
            'SELECT id FROM calendar_imports WHERE property_id = ? AND source_name = ?',
            (property_id, source_name),
        ).fetchone()['id']
        db.execute('DELETE FROM calendar_import_events WHERE import_id = ?', (import_id,))
        db.executemany(
            '''INSERT INTO calendar_import_events
               (import_id, event_uid, start_date, end_date) VALUES (?, ?, ?, ?)''',
            [(import_id, uid, start, end) for uid, start, end in events],
        )
        db.commit()
    except DB_ERRORS:
        db.rollback()
        app.logger.exception('Could not import calendar for property %s', property_id)
        flash('Calendar import failed. Existing imported dates were not changed.', 'error')
        return redirect(url_for('dashboard'))
    flash(f'Imported {len(events)} blocked date range(s) from {source_name}.', 'success')
    return redirect(url_for('dashboard'))


@app.route('/calendar/import/<int:import_id>/delete', methods=['POST'])
@landlord_required
def delete_calendar_import(import_id):
    db = get_db()
    deleted = db.execute(
        '''DELETE FROM calendar_imports
           WHERE id = ? AND property_id IN (
               SELECT id FROM properties WHERE owner_id = ?
           )''',
        (import_id, g.user['id']),
    )
    db.commit()
    flash('Imported calendar removed.' if deleted.rowcount else 'Imported calendar not found.', 'info')
    return redirect(url_for('dashboard'))


@app.route('/property/<int:property_id>/seasonal-pricing/add', methods=['POST'])
@landlord_required
def add_seasonal_pricing(property_id):
    db = get_db()
    property_row = db.execute(
        'SELECT id, price_period FROM properties WHERE id = ? AND owner_id = ?',
        (property_id, g.user['id']),
    ).fetchone()
    if not property_row:
        flash('Listing not found or unauthorized.', 'error')
        return redirect(url_for('dashboard'))
    start_date = parse_iso_date(request.form.get('start_date'))
    end_date = parse_iso_date(request.form.get('end_date'))
    try:
        price = parse_nonnegative_money(request.form.get('price'), 'Seasonal price')
        minimum_stay = int(request.form.get('minimum_stay') or 1)
    except (ValueError, TypeError):
        flash('Enter a valid seasonal price and minimum stay.', 'error')
        return redirect(url_for('dashboard'))
    max_stay = 24 if property_row['price_period'] == 'month' else 365
    if (not start_date or not end_date or end_date <= start_date
            or (end_date - start_date).days > 366
            or not 1 <= minimum_stay <= max_stay):
        flash(f'Choose a valid date range (up to 366 days) and minimum stay (1-{max_stay}).', 'error')
        return redirect(url_for('dashboard'))
    overlap = db.execute(
        '''SELECT id FROM seasonal_pricing
           WHERE property_id = ? AND start_date < ? AND end_date > ? LIMIT 1''',
        (property_id, end_date.isoformat(), start_date.isoformat()),
    ).fetchone()
    if overlap:
        flash('Seasonal pricing date ranges cannot overlap. Edit or remove the existing range first.', 'error')
        return redirect(url_for('dashboard'))
    db.execute(
        '''INSERT INTO seasonal_pricing
           (property_id, start_date, end_date, price, minimum_stay)
           VALUES (?, ?, ?, ?, ?)''',
        (property_id, start_date.isoformat(), end_date.isoformat(), price, minimum_stay),
    )
    db.commit()
    flash('Seasonal price and minimum stay saved.', 'success')
    return redirect(url_for('dashboard'))


@app.route('/property/<int:property_id>/seasonal-pricing/<int:rule_id>/delete', methods=['POST'])
@landlord_required
def delete_seasonal_pricing(property_id, rule_id):
    db = get_db()
    deleted = db.execute(
        '''DELETE FROM seasonal_pricing
           WHERE id = ? AND property_id = ?
             AND property_id IN (SELECT id FROM properties WHERE owner_id = ?)''',
        (rule_id, property_id, g.user['id']),
    )
    db.commit()
    flash('Seasonal pricing removed.' if deleted.rowcount else 'Pricing rule not found.', 'info')
    return redirect(url_for('dashboard'))


@app.route('/property/<int:property_id>/price-quote')
@login_required
def property_price_quote(property_id):
    db = get_db()
    property_row = db.execute(
        'SELECT * FROM properties WHERE id = ? AND is_active = 1',
        (property_id,),
    ).fetchone()
    check_in = parse_iso_date(request.args.get('check_in'))
    requested_unit = (request.args.get('unit') or '').strip().lower()
    try:
        duration = int(request.args.get('duration', ''))
    except (TypeError, ValueError):
        duration = 0
    if not property_row or not check_in or check_in < date.today():
        return jsonify({'error': 'Choose a valid future date and stay duration.'}), 400
    is_hourly = requested_unit == 'hour' and supports_hourly_booking(property_row)
    if is_hourly:
        if not MIN_HOURLY_STAY_HOURS <= duration <= MAX_HOURLY_STAY_HOURS:
            return jsonify({'error': f'Hourly stays must be between {MIN_HOURLY_STAY_HOURS} and {MAX_HOURLY_STAY_HOURS} hours.'}), 400
    else:
        max_duration = 60 if property_row['price_period'] == 'month' else 365
        if not 1 <= duration <= max_duration:
            return jsonify({'error': 'Choose a valid future date and stay duration.'}), 400
    try:
        quote = quote_property_stay(
            db, property_row, check_in, duration,
            duration_unit_override=('hour' if is_hourly else None),
        )
    except ValueError as error:
        return jsonify({'error': str(error)}), 400
    return jsonify({
        'base_amount': quote['base_amount'],
        'service_fee': quote['service_fee'],
        'cleaning_fee': quote['cleaning_fee'],
        'total_price': quote['total_price'],
        'minimum_stay': quote['minimum_stay'],
        'duration_unit': quote['duration_unit'],
        'unit_price': quote['unit_price'],
        'check_out': quote['check_out'].isoformat(),
    })


@app.route('/availability/<int:property_id>/block-range', methods=['POST'])
@landlord_required
def block_date_range(property_id):
    check_in = parse_iso_date(request.form.get('start_date'))
    check_out = parse_iso_date(request.form.get('end_date'))
    if not check_in or not check_out or check_in < date.today() or check_out < check_in:
        flash('Choose a valid future date range.', 'error')
        return redirect(url_for('dashboard'))
    if (check_out - check_in).days > 365:
        flash('A date range cannot exceed 366 days.', 'error')
        return redirect(url_for('dashboard'))

    db = get_db()
    owner = db.execute(
        'SELECT id FROM properties WHERE id = ? AND owner_id = ?',
        (property_id, g.user['id']),
    ).fetchone()
    if not owner:
        flash('Unauthorized.', 'error')
        return redirect(url_for('dashboard'))

    try:
        db.execute('BEGIN IMMEDIATE')
        occupied = db.execute(
            '''SELECT id FROM bookings
               WHERE property_id = ? AND booking_status IN ('pending', 'confirmed')
                 AND check_in <= ? AND check_out > ? LIMIT 1''',
            (property_id, check_out.isoformat(), check_in.isoformat()),
        ).fetchone()
        if occupied:
            db.rollback()
            flash('That range overlaps a pending request or confirmed stay.', 'error')
            return redirect(url_for('dashboard'))

        current = check_in
        while current <= check_out:
            db.execute(
                '''INSERT OR IGNORE INTO availability (property_id, date, status)
                   VALUES (?, ?, 'blocked')''',
                (property_id, current.isoformat()),
            )
            current += timedelta(days=1)
        db.commit()
        flash(f'Availability blocked from {check_in.isoformat()} through {check_out.isoformat()}.', 'success')
    except DB_ERRORS:
        db.rollback()
        app.logger.exception('Could not block date range for property %s', property_id)
        flash('Could not block those dates. Please try again.', 'error')
    return redirect(url_for('dashboard'))


@app.route('/availability/<int:property_id>/unblock-range', methods=['POST'])
@landlord_required
def unblock_date_range(property_id):
    start_date = parse_iso_date(request.form.get('start_date'))
    end_date = parse_iso_date(request.form.get('end_date'))
    if not start_date or not end_date or end_date < start_date:
        flash('Choose a valid date range to unblock.', 'error')
        return redirect(url_for('dashboard'))
    if (end_date - start_date).days > 365:
        flash('A date range cannot exceed 366 days.', 'error')
        return redirect(url_for('dashboard'))

    db = get_db()
    owner = db.execute(
        'SELECT id FROM properties WHERE id = ? AND owner_id = ?',
        (property_id, g.user['id']),
    ).fetchone()
    if not owner:
        flash('Unauthorized.', 'error')
        return redirect(url_for('dashboard'))

    db.execute(
        '''DELETE FROM availability
           WHERE property_id = ? AND status = 'blocked'
             AND date >= ? AND date <= ?''',
        (property_id, start_date.isoformat(), end_date.isoformat()),
    )
    db.commit()
    flash(f'Blocked dates released from {start_date.isoformat()} through {end_date.isoformat()}.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/unblock_date/<int:property_id>', methods=['POST'])
@landlord_required
def unblock_date(property_id):
    unblocked_date = request.form.get('date')
    db = get_db()
    owner = db.execute('SELECT id FROM properties WHERE id = ? AND owner_id = ?',
                        (property_id, g.user['id'])).fetchone()
    if not owner:
        flash('Unauthorized.', 'error')
        return redirect(url_for('dashboard'))
    db.execute('DELETE FROM availability WHERE property_id = ? AND date = ? AND status = "blocked"',
               (property_id, unblocked_date))
    db.commit()
    flash('Date unblocked.', 'success')
    return redirect(url_for('dashboard'))

# --- Admin ---
def admin_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            flash('Please log in with an administrator account to access the admin dashboard.', 'info')
            return redirect(url_for('login'))
        if not g.user['is_admin']:
            flash('Admin access required.', 'error')
            return redirect(_home_dashboard_url(g.user))
        return view(**kwargs)
    return wrapped_view

def _sync_admin_payout_ledger(db):
    db.execute(
        '''INSERT OR IGNORE INTO payout_ledger (booking_id, owner_id, amount, status)
           SELECT b.id, p.owner_id,
                  CASE WHEN b.base_amount + b.cleaning_fee > 0
                       THEN b.base_amount + b.cleaning_fee ELSE 0 END,
                  'pending'
           FROM bookings b
           JOIN properties p ON p.id = b.property_id
           WHERE b.booking_status = 'confirmed' AND b.payment_status = 'paid'
             AND b.refund_status NOT IN ('processing', 'refunded')'''
    )
    db.commit()


def _get_admin_nav_counts(db):
    total_users = db.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    total_properties = db.execute('SELECT COUNT(*) FROM properties').fetchone()[0]
    total_bookings = db.execute('SELECT COUNT(*) FROM bookings').fetchone()[0]
    pending_payments = db.execute(
        '''SELECT COUNT(*) FROM bookings
           WHERE payment_status = 'pending' AND booking_status IN ('pending', 'confirmed')'''
    ).fetchone()[0]
    pending_refunds = db.execute(
        "SELECT COUNT(*) FROM bookings WHERE refund_status IN ('requested', 'processing')"
    ).fetchone()[0]
    pending_payouts = db.execute(
        "SELECT COUNT(*) FROM payout_ledger WHERE status = 'pending'"
    ).fetchone()[0]
    pending_verifications = db.execute(
        "SELECT COUNT(*) FROM users WHERE host_verification_status = 'pending'"
    ).fetchone()[0]
    open_reports = db.execute(
        "SELECT COUNT(*) FROM property_reports WHERE status = 'open'"
    ).fetchone()[0]
    open_support = db.execute(
        "SELECT COUNT(*) FROM support_requests WHERE status IN ('open', 'in_review')"
    ).fetchone()[0]
    pending_payments_tab = pending_payments + pending_refunds + pending_payouts
    pending_moderation_tab = pending_verifications + open_reports + open_support
    return {
        'total_users': total_users,
        'total_properties': total_properties,
        'total_bookings': total_bookings,
        'pending_payments_count': pending_payments,
        'pending_refunds_count': pending_refunds,
        'pending_payouts_count': pending_payouts,
        'pending_verifications_count': pending_verifications,
        'open_reports_count': open_reports,
        'open_support_count': open_support,
        'pending_payments_tab': pending_payments_tab,
        'pending_moderation_tab': pending_moderation_tab,
        'pending_actions': pending_payments_tab + pending_moderation_tab,
    }


@app.route('/admin')
@admin_required
def admin_dashboard():
    db = get_db()
    _sync_admin_payout_ledger(db)
    admin_nav = _get_admin_nav_counts(db)

    recent_users = db.execute(
        '''SELECT id, full_name, email, phone, role, is_admin, created_at
           FROM users ORDER BY created_at DESC LIMIT 6'''
    ).fetchall()
    recent_properties = db.execute(
        '''SELECT p.id, p.title, p.compound, p.price_per_night, p.price_period,
                  p.image_main, p.is_verified, p.is_active
           FROM properties p ORDER BY p.created_at DESC LIMIT 6'''
    ).fetchall()
    try:
        recent_audit_logs = db.execute(
            '''SELECT id, admin_id, admin_email, action, target_type, target_id,
                      details, ip_address, created_at
               FROM admin_audit_logs
               ORDER BY created_at DESC, id DESC LIMIT 6'''
        ).fetchall()
    except DB_ERRORS:
        recent_audit_logs = []

    user_breakdown = db.execute(
        '''SELECT
               SUM(CASE WHEN role = 'owner' THEN 1 ELSE 0 END) AS total_hosts,
               SUM(CASE WHEN role = 'tenant' THEN 1 ELSE 0 END) AS total_tenants,
               SUM(CASE WHEN role = 'banned' THEN 1 ELSE 0 END) AS banned_users,
               SUM(CASE WHEN is_admin = 1 THEN 1 ELSE 0 END) AS admin_users
           FROM users'''
    ).fetchone()
    prop_breakdown = db.execute(
        '''SELECT
               SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) AS active_properties,
               SUM(CASE WHEN is_verified = 1 THEN 1 ELSE 0 END) AS verified_properties
           FROM properties'''
    ).fetchone()
    booking_breakdown = db.execute(
        '''SELECT
               SUM(CASE WHEN booking_status = 'confirmed' THEN 1 ELSE 0 END) AS confirmed_bookings,
               SUM(CASE WHEN payment_status = 'paid' THEN COALESCE(total_price, 0) ELSE 0 END) AS paid_revenue
           FROM bookings'''
    ).fetchone()

    admin_stats = {
        **admin_nav,
        'total_hosts': user_breakdown['total_hosts'] or 0,
        'total_tenants': user_breakdown['total_tenants'] or 0,
        'banned_users': user_breakdown['banned_users'] or 0,
        'admin_users': user_breakdown['admin_users'] or 0,
        'active_properties': prop_breakdown['active_properties'] or 0,
        'verified_properties': prop_breakdown['verified_properties'] or 0,
        'confirmed_bookings': booking_breakdown['confirmed_bookings'] or 0,
        'paid_revenue': float(booking_breakdown['paid_revenue'] or 0),
    }
    return render_template(
        'admin/overview.html',
        admin_nav=admin_nav,
        admin_stats=admin_stats,
        recent_users=recent_users,
        recent_properties=recent_properties,
        recent_audit_logs=recent_audit_logs,
    )


@app.route('/admin/listings')
@admin_required
def admin_listings():
    db = get_db()
    admin_nav = _get_admin_nav_counts(db)
    properties = db.execute('''
        SELECT p.*, u.full_name AS owner_name, u.email AS owner_email
        FROM properties p
        LEFT JOIN users u ON u.id = p.owner_id
        ORDER BY p.created_at DESC
    ''').fetchall()
    return render_template('admin/listings.html', admin_nav=admin_nav, properties=properties)


@app.route('/admin/bookings')
@admin_required
def admin_bookings():
    db = get_db()
    admin_nav = _get_admin_nav_counts(db)
    bookings = db.execute('''
        SELECT b.*, p.title AS property_title, u.full_name AS tenant_name, u.email AS tenant_email
        FROM bookings b
        LEFT JOIN properties p ON p.id = b.property_id
        LEFT JOIN users u ON u.id = b.user_id
        ORDER BY b.created_at DESC
    ''').fetchall()
    return render_template('admin/bookings.html', admin_nav=admin_nav, bookings=bookings)


@app.route('/admin/accounting')
@admin_required
def admin_accounting():
    db = get_db()
    _sync_admin_payout_ledger(db)
    admin_nav = _get_admin_nav_counts(db)

    payment_review_bookings = db.execute('''
        SELECT b.id, b.total_price, b.tx_ref, b.booking_status,
               b.payment_method, b.payment_claim_reference, b.payment_claim_submitted_at,
               u.full_name AS tenant_name, p.title AS property_title
        FROM bookings b
        JOIN users u ON u.id = b.user_id
        JOIN properties p ON p.id = b.property_id
        WHERE b.payment_status = 'pending'
          AND b.booking_status IN ('pending', 'confirmed')
        ORDER BY b.created_at
    ''').fetchall()
    refund_requests = db.execute('''
        SELECT b.id, b.total_price, b.tx_ref, b.refund_status, b.refund_reference,
               b.payment_reference, b.check_in, b.check_out, b.payment_method, p.cancellation_policy,
               u.full_name AS tenant_name, p.title AS property_title
        FROM bookings b
        JOIN users u ON u.id = b.user_id
        JOIN properties p ON p.id = b.property_id
        WHERE b.refund_status IN ('requested', 'processing')
        ORDER BY b.created_at
    ''').fetchall()
    payout_ledger = db.execute('''
        SELECT pl.*, p.title AS property_title, host.full_name AS host_name,
               b.tx_ref, b.check_in
        FROM payout_ledger pl
        JOIN bookings b ON b.id = pl.booking_id
        JOIN properties p ON p.id = b.property_id
        JOIN users host ON host.id = pl.owner_id
        ORDER BY CASE pl.status WHEN 'pending' THEN 0 ELSE 1 END, pl.created_at
    ''').fetchall()

    paid_totals = db.execute(
        '''SELECT COUNT(*) AS cnt,
                  SUM(COALESCE(total_price, 0)) AS volume,
                  SUM(COALESCE(service_fee, 0)) AS fees
           FROM bookings WHERE payment_status = 'paid' '''
    ).fetchone()
    accounting_summary = {
        'paid_bookings_count': paid_totals['cnt'] or 0,
        'paid_volume': float(paid_totals['volume'] or 0),
        'service_fee_revenue': float(paid_totals['fees'] or 0),
        'pending_payouts_count': sum(1 for pl in payout_ledger if pl['status'] == 'pending'),
        'pending_payouts_total': sum(float(pl['amount'] or 0) for pl in payout_ledger if pl['status'] == 'pending'),
        'paid_payouts_count': sum(1 for pl in payout_ledger if pl['status'] == 'paid'),
        'paid_payouts_total': sum(float(pl['amount'] or 0) for pl in payout_ledger if pl['status'] == 'paid'),
    }
    return render_template(
        'admin/accounting.html',
        admin_nav=admin_nav,
        accounting_summary=accounting_summary,
        payment_review_bookings=payment_review_bookings,
        refund_requests=refund_requests,
        payout_ledger=payout_ledger,
    )


@app.route('/admin/users')
@admin_required
def admin_users():
    db = get_db()
    admin_nav = _get_admin_nav_counts(db)
    users = db.execute(
        '''SELECT id, full_name, email, phone, role, profile_pic, is_admin,
                  host_verification_status, host_verification_note,
                  email_verified_at, phone_verified_at, created_at
           FROM users ORDER BY created_at DESC'''
    ).fetchall()
    return render_template('admin/users.html', admin_nav=admin_nav, users=users)


@app.route('/admin/moderation')
@admin_required
def admin_moderation():
    db = get_db()
    admin_nav = _get_admin_nav_counts(db)
    verification_requests = db.execute(
        '''SELECT id, full_name, email, phone, host_verification_note
           FROM users WHERE host_verification_status = 'pending'
           ORDER BY created_at'''
    ).fetchall()
    reports = db.execute('''
        SELECT r.*, p.title AS property_title, u.full_name AS reporter_name
        FROM property_reports r
        JOIN properties p ON p.id = r.property_id
        JOIN users u ON u.id = r.reporter_id
        ORDER BY CASE r.status WHEN 'open' THEN 0 ELSE 1 END, r.created_at DESC
    ''').fetchall()
    support_requests = db.execute('''
        SELECT sr.*, reporter.full_name AS reporter_name, b.tx_ref,
               p.title AS property_title
        FROM support_requests sr
        JOIN users reporter ON reporter.id = sr.reporter_id
        LEFT JOIN bookings b ON b.id = sr.booking_id
        LEFT JOIN properties p ON p.id = b.property_id
        ORDER BY CASE sr.status WHEN 'open' THEN 0 WHEN 'in_review' THEN 1 ELSE 2 END,
                 sr.created_at DESC
    ''').fetchall()
    return render_template(
        'admin/moderation.html',
        admin_nav=admin_nav,
        verification_requests=verification_requests,
        reports=reports,
        support_requests=support_requests,
    )


@app.route('/admin/audit')
@admin_required
def admin_audit_log():
    db = get_db()
    admin_nav = _get_admin_nav_counts(db)
    try:
        audit_logs = db.execute(
            '''SELECT id, admin_id, admin_email, action, target_type, target_id,
                      details, ip_address, created_at
               FROM admin_audit_logs
               ORDER BY created_at DESC, id DESC LIMIT 100'''
        ).fetchall()
    except DB_ERRORS:
        audit_logs = []
    return render_template('admin/audit.html', admin_nav=admin_nav, audit_logs=audit_logs)


@app.route('/admin/settings')
@admin_required
def admin_settings():
    db = get_db()
    admin_nav = _get_admin_nav_counts(db)
    pending_totp_secret = session.get('pending_totp_setup_secret')
    pending_totp_uri = (
        build_otpauth_uri(g.user['email'], pending_totp_secret)
        if pending_totp_secret else None
    )
    return render_template(
        'admin/settings.html',
        admin_nav=admin_nav,
        phone_countries=phone_country_options(),
        admin_totp_enabled=_user_totp_enabled(g.user),
        pending_totp_secret=pending_totp_secret,
        pending_totp_uri=pending_totp_uri,
    )


@app.route('/admin/settings/profile', methods=['POST'])
@admin_required
def admin_update_profile():
    if not check_rate_limit('admin_profile_update', str(g.user['id']), 15, 900):
        abort(429, description='Too many profile update attempts. Please wait a few minutes.')
    full_name = request.form.get('full_name', '').strip()
    new_email = request.form.get('email', '').strip().lower()
    phone_raw = request.form.get('phone', '').strip()
    country_region = request.form.get('country_region', 'ZM').upper()
    profile_pic_raw = request.form.get('profile_pic', '').strip()
    current_password = request.form.get('current_password', '')

    if not full_name or len(full_name) > 120:
        flash('Enter a valid full name (up to 120 characters).', 'error')
        return redirect(url_for('admin_settings'))
    if not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', new_email) or len(new_email) > 254:
        flash('Enter a valid email address.', 'error')
        return redirect(url_for('admin_settings'))
    try:
        phone = normalize_phone_number(phone_raw, country_region)
        profile_pic = validate_image_url(profile_pic_raw, allow_empty=True)
    except ValueError as error:
        flash(str(error), 'error')
        return redirect(url_for('admin_settings'))

    old_email = (g.user['email'] or '').strip().lower()
    email_changed = new_email != old_email
    phone_changed = phone != (g.user['phone'] or '')

    if email_changed and not check_password_hash(g.user['password'], current_password):
        flash('Enter your current password to change your administrator email address.', 'error')
        return redirect(url_for('admin_settings'))

    db = get_db()
    if email_changed:
        existing = db.execute(
            'SELECT id FROM users WHERE LOWER(email) = ? AND id != ?',
            (new_email, g.user['id']),
        ).fetchone()
        if existing:
            flash('Another account already uses that email address.', 'error')
            return redirect(url_for('admin_settings'))

    new_sv = _user_session_version(g.user) + (1 if email_changed else 0)
    try:
        db.execute(
            '''UPDATE users
               SET full_name = ?, email = ?, phone = ?, profile_pic = ?,
                   email_verified_at = CASE WHEN ? THEN NULL ELSE email_verified_at END,
                   phone_verified_at = CASE WHEN ? THEN NULL ELSE phone_verified_at END,
                   session_version = ?
               WHERE id = ?''',
            (
                full_name, new_email, phone, profile_pic or None,
                1 if email_changed else 0,
                1 if phone_changed else 0,
                new_sv, g.user['id'],
            ),
        )
        action = 'admin_email_changed' if email_changed else 'admin_profile_updated'
        details = f'{old_email} -> {new_email}' if email_changed else f'Updated contact details ({phone})'
        log_admin_action(db, action, 'user', g.user['id'], details)
        db.commit()
    except DB_INTEGRITY_ERRORS:
        db.rollback()
        flash('Another account already uses that email address.', 'error')
        return redirect(url_for('admin_settings'))

    if email_changed:
        session['session_version'] = new_sv
        session.pop('pending_totp_setup_secret', None)
    flash('Administrator account details updated successfully.', 'success')
    return redirect(url_for('admin_settings'))


@app.route('/admin/settings/password', methods=['POST'])
@admin_required
def admin_change_password():
    if not check_rate_limit('change_password_user', str(g.user['id']), 10, 900):
        abort(429, description='Too many password change attempts. Please wait and try again.')
    current = request.form.get('current_password', '')
    new_pw = request.form.get('new_password', '')
    confirm = request.form.get('confirm_password', '')

    if not check_password_hash(g.user['password'], current):
        flash('Current password is incorrect.', 'error')
        return redirect(url_for('admin_settings'))
    password_error = validate_password_strength(new_pw)
    if password_error:
        flash(password_error, 'error')
        return redirect(url_for('admin_settings'))
    if new_pw != confirm:
        flash('Passwords do not match.', 'error')
        return redirect(url_for('admin_settings'))

    db = get_db()
    user_id = g.user['id']
    new_sv = _user_session_version(g.user) + 1
    db.execute(
        'UPDATE users SET password = ?, session_version = ? WHERE id = ?',
        (generate_password_hash(new_pw), new_sv, user_id),
    )
    log_admin_action(db, 'admin_password_changed', 'user', user_id)
    db.commit()

    was_permanent = session.permanent
    session.clear()
    now = time.time()
    session['user_id'] = user_id
    session['session_version'] = new_sv
    session['_session_created_at'] = now
    session['_session_last_active'] = now
    session.permanent = was_permanent
    csrf_token()
    flash('Administrator password changed successfully. Other sessions have been signed out.', 'success')
    return redirect(url_for('admin_settings'))


@app.route('/admin/security/2fa/start', methods=['POST'])
@admin_required
def admin_start_2fa():
    if _user_totp_enabled(g.user):
        flash('Two-factor authentication is already enabled on your account.', 'info')
        return redirect(url_for('admin_settings'))
    session['pending_totp_setup_secret'] = generate_totp_secret()
    flash('Scan or enter the setup key in your authenticator app, then confirm with a 6-digit code.', 'info')
    return redirect(url_for('admin_settings'))


@app.route('/admin/security/2fa/confirm', methods=['POST'])
@admin_required
def admin_confirm_2fa():
    pending_secret = session.get('pending_totp_setup_secret')
    if not pending_secret:
        flash('Start 2FA setup first before confirming.', 'error')
        return redirect(url_for('admin_settings'))
    current_password = request.form.get('current_password', '')
    code = request.form.get('totp_code', '').strip()
    if not check_password_hash(g.user['password'], current_password):
        flash('Current password is incorrect.', 'error')
        return redirect(url_for('admin_settings'))
    if not verify_totp_code(pending_secret, code):
        flash('Invalid 6-digit code. Check your authenticator app time sync and try again.', 'error')
        return redirect(url_for('admin_settings'))
    db = get_db()
    db.execute(
        'UPDATE users SET totp_secret = ?, totp_enabled = 1 WHERE id = ?',
        (pending_secret, g.user['id']),
    )
    log_admin_action(db, 'admin_2fa_enabled', 'user', g.user['id'])
    db.commit()
    session.pop('pending_totp_setup_secret', None)
    flash('Two-factor authentication is now enabled for your admin account.', 'success')
    return redirect(url_for('admin_settings'))


@app.route('/admin/security/2fa/disable', methods=['POST'])
@admin_required
def admin_disable_2fa():
    if not _user_totp_enabled(g.user):
        flash('Two-factor authentication is not enabled.', 'info')
        return redirect(url_for('admin_settings'))
    current_password = request.form.get('current_password', '')
    code = request.form.get('totp_code', '').strip()
    if not check_password_hash(g.user['password'], current_password):
        flash('Current password is incorrect.', 'error')
        return redirect(url_for('admin_settings'))
    if not verify_totp_code(g.user['totp_secret'], code):
        flash('Invalid 6-digit authenticator code.', 'error')
        return redirect(url_for('admin_settings'))
    db = get_db()
    new_sv = _user_session_version(g.user) + 1
    db.execute(
        'UPDATE users SET totp_secret = NULL, totp_enabled = 0, session_version = ? WHERE id = ?',
        (new_sv, g.user['id']),
    )
    log_admin_action(db, 'admin_2fa_disabled', 'user', g.user['id'])
    db.commit()
    session['session_version'] = new_sv
    flash('Two-factor authentication has been disabled.', 'info')
    return redirect(url_for('admin_settings'))


@app.route('/admin/payout/<int:ledger_id>/mark-paid', methods=['POST'])
@admin_required
def mark_payout_paid(ledger_id):
    reference = request.form.get('reference', '').strip()
    if not reference or len(reference) > 160:
        flash('Enter the payout provider reference (up to 160 characters).', 'error')
        return redirect(url_for('admin_accounting'))
    db = get_db()
    ledger = db.execute(
        '''SELECT pl.id, pl.status, b.payment_status, b.booking_status,
                  b.refund_status
           FROM payout_ledger pl JOIN bookings b ON b.id = pl.booking_id
           WHERE pl.id = ?''',
        (ledger_id,),
    ).fetchone()
    if (not ledger or ledger['status'] != 'pending'
            or ledger['payment_status'] != 'paid'
            or ledger['booking_status'] != 'confirmed'
            or ledger['refund_status'] in ('processing', 'refunded')):
        flash('This payout is not eligible to be marked complete.', 'error')
        return redirect(url_for('admin_accounting'))
    db.execute(
        '''UPDATE payout_ledger SET status = 'paid', reference = ?,
           paid_at = CURRENT_TIMESTAMP WHERE id = ? AND status = 'pending' ''',
        (reference, ledger_id),
    )
    log_admin_action(db, 'payout_marked_paid', 'payout_ledger', ledger_id, f'Reference: {reference}')
    db.commit()
    flash('Payout marked complete with provider reference recorded.', 'success')
    return redirect(url_for('admin_accounting'))

@app.route('/admin/verify_property/<int:property_id>', methods=['POST'])
@admin_required
def verify_property(property_id):
    db = get_db()
    property = db.execute('SELECT title FROM properties WHERE id = ?', (property_id,)).fetchone()
    if not property:
        flash('Property not found.', 'error')
        return redirect(url_for('admin_listings'))
    db.execute('UPDATE properties SET is_verified = 1 WHERE id = ?', (property_id,))
    log_admin_action(db, 'property_verified', 'property', property_id, property['title'])
    db.commit()
    flash(f'Property "{property["title"]}" verified!', 'success')
    return redirect(url_for('admin_listings'))


@app.route('/admin/unverify_property/<int:property_id>', methods=['POST'])
@admin_required
def unverify_property(property_id):
    db = get_db()
    property = db.execute('SELECT title FROM properties WHERE id = ?', (property_id,)).fetchone()
    if not property:
        flash('Property not found.', 'error')
        return redirect(url_for('admin_listings'))
    db.execute('UPDATE properties SET is_verified = 0 WHERE id = ?', (property_id,))
    log_admin_action(db, 'property_unverified', 'property', property_id, property['title'])
    db.commit()
    flash(f'Verified badge removed from "{property["title"]}".', 'info')
    return redirect(url_for('admin_listings'))


@app.route('/admin/toggle_admin/<int:user_id>', methods=['POST'])
@admin_required
def admin_toggle_admin(user_id):
    if user_id == g.user['id']:
        flash('You cannot change your own administrator role.', 'error')
        return redirect(url_for('admin_users'))
    db = get_db()
    user = db.execute('SELECT id, full_name, role, is_admin FROM users WHERE id = ?', (user_id,)).fetchone()
    if not user:
        flash('User not found.', 'error')
        return redirect(url_for('admin_users'))
    if user['is_admin']:
        admin_count = db.execute('SELECT COUNT(*) FROM users WHERE is_admin = 1').fetchone()[0]
        if admin_count <= 1:
            flash('At least one administrator account must remain active.', 'error')
            return redirect(url_for('admin_users'))
        db.execute(
            'UPDATE users SET is_admin = 0, session_version = COALESCE(session_version, 1) + 1 WHERE id = ?',
            (user_id,),
        )
        log_admin_action(db, 'admin_role_revoked', 'user', user_id, user['full_name'])
        db.commit()
        flash(f'Removed admin access from "{user["full_name"]}".', 'info')
    else:
        if user['role'] == 'banned':
            flash('Unban this user before granting admin access.', 'error')
            return redirect(url_for('admin_users'))
        db.execute('UPDATE users SET is_admin = 1 WHERE id = ?', (user_id,))
        log_admin_action(db, 'admin_role_granted', 'user', user_id, user['full_name'])
        db.commit()
        flash(f'Granted admin access to "{user["full_name"]}".', 'success')
    return redirect(url_for('admin_users'))


@app.route('/admin/host-verification/<int:user_id>/<action>', methods=['POST'])
@admin_required
def review_host_verification(user_id, action):
    if action not in ('verify', 'reject'):
        flash('Invalid verification action.', 'error')
        return redirect(url_for('admin_moderation'))
    status = 'verified' if action == 'verify' else 'rejected'
    db = get_db()
    result = db.execute(
        '''UPDATE users SET host_verification_status = ?
           WHERE id = ? AND host_verification_status = 'pending' ''',
        (status, user_id),
    )
    if result.rowcount:
        log_admin_action(db, f'host_verification_{status}', 'user', user_id)
    db.commit()
    if result.rowcount:
        flash(f'Host verification marked {status}. Confirm identity and phone evidence before verifying.', 'success')
    else:
        flash('No pending verification request found.', 'info')
    return redirect(url_for('admin_moderation'))


@app.route('/admin/property-report/<int:report_id>/<action>', methods=['POST'])
@admin_required
def review_property_report(report_id, action):
    status_by_action = {'resolve': 'resolved', 'dismiss': 'dismissed'}
    if action not in status_by_action:
        flash('Invalid report action.', 'error')
        return redirect(url_for('admin_moderation'))
    db = get_db()
    db.execute('UPDATE property_reports SET status = ? WHERE id = ?',
               (status_by_action[action], report_id))
    log_admin_action(db, f'property_report_{status_by_action[action]}', 'property_report', report_id)
    db.commit()
    flash('Listing report updated.', 'success')
    return redirect(url_for('admin_moderation'))


@app.route('/admin/support-request/<int:request_id>/<action>', methods=['POST'])
@admin_required
def review_support_request(request_id, action):
    status_by_action = {'review': 'in_review', 'resolve': 'resolved', 'close': 'closed'}
    if action not in status_by_action:
        flash('Invalid support request action.', 'error')
        return redirect(url_for('admin_moderation'))
    db = get_db()
    support_request = db.execute(
        'SELECT id, reporter_id FROM support_requests WHERE id = ?', (request_id,)
    ).fetchone()
    if not support_request:
        flash('Support request not found.', 'error')
        return redirect(url_for('admin_moderation'))
    status = status_by_action[action]
    db.execute(
        '''UPDATE support_requests SET status = ?, updated_at = CURRENT_TIMESTAMP
           WHERE id = ?''',
        (status, request_id),
    )
    create_notification(
        db, support_request['reporter_id'],
        f'Your KwachaStay support request #{request_id} is now {status.replace("_", " ")}.',
        url_for('support_center'),
    )
    log_admin_action(db, f'support_request_{status}', 'support_request', request_id)
    db.commit()
    flash('Support request updated.', 'success')
    return redirect(url_for('admin_moderation'))


@app.route('/admin/refund/<int:booking_id>/<action>', methods=['POST'])
@admin_required
def process_refund(booking_id, action):
    if action not in ('mark-refunded', 'reject', 'refresh'):
        flash('Invalid refund action.', 'error')
        return redirect(url_for('admin_dashboard'))
    db = get_db()
    booking = db.execute(
        '''SELECT id, total_price, payment_status, refund_status,
                  payment_method, payment_reference, refund_reference
           FROM bookings WHERE id = ?''',
        (booking_id,),
    ).fetchone()
    if not booking:
        flash('No matching refund request found.', 'error')
    elif action == 'refresh':
        if (booking['refund_status'] != 'processing'
                or booking['payment_method'] != 'Flutterwave Mobile Money'
                or not booking['refund_reference']
                or not booking['refund_reference'].isdigit()):
            flash('This Flutterwave refund cannot be refreshed.', 'error')
            return redirect(url_for('admin_dashboard'))
        try:
            response = flutterwave_api_request('GET', f'refunds/{booking["refund_reference"]}')
            refund = response.get('data') or response
            provider_status = str(refund.get('status') or '').lower()
            if (str(refund.get('id')) != booking['refund_reference']
                    or (refund.get('transaction_id') is not None
                        and str(refund['transaction_id']) != booking['payment_reference'])):
                raise ValueError('Flutterwave returned refund details for a different transaction.')
            if provider_status in {
                    'completed-momo', 'completed-bank-transfer',
                    'completed-mpgs', 'completed-offline', 'completed-preauth'}:
                amount_refunded = round(float(refund.get('amount_refunded') or 0), 2)
                status = 'refunded' if amount_refunded >= round(booking['total_price'], 2) else 'processing'
            elif provider_status.startswith('failed'):
                status = 'requested'
            elif provider_status in {
                    'completed', 'pending-momo', 'pending-bank-transfer',
                    'pending-mpgs', 'processing'}:
                status = 'processing'
            else:
                raise ValueError('Flutterwave returned an unrecognized refund status.')
            db.execute(
                '''UPDATE bookings SET refund_status = ?
                   WHERE id = ? AND refund_status = 'processing' ''',
                (status, booking_id),
            )
            db.commit()
            flash(f'Flutterwave refund status: {provider_status}.', 'success')
        except (RuntimeError, ValueError, TypeError) + DB_ERRORS:
            db.rollback()
            app.logger.exception('Could not refresh Flutterwave refund for booking %s', booking_id)
            flash('Could not refresh the provider refund status. No refund status was changed.', 'error')
    elif booking['refund_status'] != 'requested':
        flash('No pending refund request found.', 'error')
    elif action == 'mark-refunded' and booking['payment_status'] != 'paid':
        flash('Only verified paid bookings can be marked refunded.', 'error')
    elif action == 'mark-refunded' and booking['payment_method'] == 'Flutterwave Mobile Money':
        try:
            if not booking['payment_reference'] or not booking['payment_reference'].isdigit():
                raise ValueError('The verified Flutterwave transaction ID is missing.')
            db.execute('BEGIN IMMEDIATE')
            claimed = db.execute(
                '''UPDATE bookings SET refund_status = 'processing', refund_reference = NULL
                   WHERE id = ? AND refund_status = 'requested' ''',
                (booking_id,),
            )
            if claimed.rowcount != 1:
                db.rollback()
                flash('This refund request is already being processed.', 'info')
                return redirect(url_for('admin_dashboard'))
            db.commit()
            response = flutterwave_api_request(
                'POST',
                f'transactions/{booking["payment_reference"]}/refund',
                {
                    'amount': booking['total_price'],
                    'comments': f'KwachaStay booking #{booking_id} refund',
                },
            )
            refund = response.get('data') or {}
            provider_status = str(refund.get('status') or '').lower()
            if not refund.get('id') or not provider_status:
                raise RuntimeError('Flutterwave did not return a refund status.')
            completed_statuses = {
                'completed-momo', 'completed-bank-transfer',
                'completed-mpgs', 'completed-offline', 'completed-preauth',
            }
            refund_status = 'refunded' if provider_status in completed_statuses else 'processing'
            updated = db.execute(
                '''UPDATE bookings SET refund_status = ?, refund_reference = ?
                   WHERE id = ? AND refund_status = 'processing' ''',
                (refund_status, str(refund['id']), booking_id),
            )
            if updated.rowcount != 1:
                db.rollback()
                flash('Provider accepted the refund, but the local status changed. Check the provider before retrying.', 'error')
                return redirect(url_for('admin_dashboard'))
            log_admin_action(db, f'refund_{refund_status}', 'booking', booking_id, f'Flutterwave refund #{refund["id"]}')
            db.commit()
            flash(
                'Flutterwave refund completed.' if refund_status == 'refunded'
                else f'Flutterwave accepted the refund; provider status: {provider_status}.',
                'success',
            )
        except (RuntimeError, ValueError) + DB_ERRORS:
            db.rollback()
            app.logger.exception('Could not initiate Flutterwave refund for booking %s', booking_id)
            flash('Flutterwave did not confirm the refund request. Its status remains processing to prevent duplicate refunds; reconcile it in the provider dashboard.', 'error')
    else:
        next_status = 'refunded' if action == 'mark-refunded' else 'rejected'
        db.execute(
            '''UPDATE bookings SET refund_status = ?, refund_reference = NULL
               WHERE id = ? AND refund_status = 'requested' ''',
            (next_status, booking_id),
        )
        log_admin_action(db, f'refund_{next_status}', 'booking', booking_id)
        db.commit()
        if action == 'mark-refunded':
            flash('Refund marked complete after manual provider-side processing.', 'success')
        else:
            flash('Refund request rejected.', 'info')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/payment/<int:booking_id>/verify', methods=['POST'])
@admin_required
def verify_booking_payment(booking_id):
    payment_reference = request.form.get('payment_reference', '').strip()
    payment_method = request.form.get('payment_method', '').strip()
    if not payment_reference or len(payment_reference) > 160:
        flash('Enter the provider transaction reference (up to 160 characters).', 'error')
        return redirect(url_for('admin_dashboard'))
    if payment_method not in ('MTN Mobile Money', 'Airtel Money', 'Bank Transfer', 'Card', 'Other'):
        flash('Choose a valid payment method.', 'error')
        return redirect(url_for('admin_dashboard'))

    db = get_db()
    expire_pending_booking_requests(db, force=True)
    booking = db.execute(
        'SELECT id, payment_status, booking_status FROM bookings WHERE id = ?',
        (booking_id,),
    ).fetchone()
    if not booking or booking['payment_status'] != 'pending' or booking['booking_status'] in ('declined', 'cancelled'):
        flash('This booking cannot be marked paid.', 'error')
        return redirect(url_for('admin_dashboard'))
    try:
        result = db.execute(
            '''UPDATE bookings SET payment_status = 'paid', payment_reference = ?, payment_method = ?,
                   refund_status = CASE
                       WHEN booking_status IN ('declined', 'cancelled', 'expired') THEN 'requested'
                       ELSE refund_status
                   END
               WHERE id = ? AND payment_status = 'pending' ''',
            (payment_reference, payment_method, booking_id),
        )
        if result.rowcount != 1:
            db.rollback()
            flash('Payment status changed while you were reviewing. Refresh and try again.', 'error')
            return redirect(url_for('admin_dashboard'))
        log_admin_action(db, 'payment_verified', 'booking', booking_id, f'{payment_method}: {payment_reference}')
        db.commit()
        flash('Payment recorded as verified. This action records your provider-side verification; it does not charge the guest.', 'success')
    except DB_INTEGRITY_ERRORS:
        db.rollback()
        flash('That provider reference is already linked to another booking.', 'error')
    except DB_ERRORS:
        db.rollback()
        app.logger.exception('Could not record payment verification for booking %s', booking_id)
        flash('Could not record payment verification. Please try again.', 'error')
    return redirect(url_for('admin_dashboard'))

# --- Notification Helper ---
def create_notification(db, user_id, message, link=None):
    db.execute('INSERT INTO notifications (user_id, message, link) VALUES (?, ?, ?)',
               (user_id, message, link))


# --- Context Processor: Inject unread counts globally ---
@app.context_processor
def inject_unread_counts():
    counts = {
        'unread_messages': 0,
        'unread_notifications': 0,
        'service_fee': BOOKING_SERVICE_FEE,
        'booking_request_expiry_hours': BOOKING_REQUEST_EXPIRY_HOURS,
        'power_backup_options': POWER_BACKUP_OPTIONS,
        'water_supply_options': WATER_SUPPLY_OPTIONS,
        'internet_options': INTERNET_OPTIONS,
        'self_checkin_options': SELF_CHECKIN_OPTIONS,
        'mobile_money_enabled': flutterwave_checkout_enabled(),
        'bank_transfer_enabled': BANK_TRANSFER_ENABLED,
        'payment_whatsapp_number': PAYMENT_WHATSAPP_NUMBER,
        'uploads_enabled': app.config['UPLOADS_ENABLED'],
        'phone_verification_enabled': bool(
            TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_FROM_NUMBER
        ),
        'low_data_mode': bool(session.get('low_data_mode')),
        'csrf_token': csrf_token,
        'csp_nonce': csp_nonce,
    }
    if getattr(g, 'user', None):
        db = get_db()
        counts['unread_messages'] = db.execute(
            'SELECT COUNT(*) FROM messages WHERE receiver_id = ? AND is_read = 0',
            (g.user['id'],)
        ).fetchone()[0]
        counts['unread_notifications'] = db.execute(
            'SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0',
            (g.user['id'],)
        ).fetchone()[0]
    return counts


@app.template_filter('listing_image')
def listing_image_url(image_url):
    if not image_url or not session.get('low_data_mode'):
        return image_url
    parsed = urllib.parse.urlsplit(image_url)
    if parsed.scheme != 'https' or parsed.hostname not in ('images.unsplash.com',):
        return image_url
    query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    query.update({'auto': ['format'], 'fit': ['crop'], 'w': ['480'], 'q': ['50']})
    return urllib.parse.urlunsplit((
        parsed.scheme, parsed.netloc, parsed.path,
        urllib.parse.urlencode(query, doseq=True), parsed.fragment,
    ))


@app.route('/preferences/low-data', methods=['POST'])
def toggle_low_data_mode():
    enabled = request.form.get('enabled') == '1'
    session['low_data_mode'] = enabled
    referrer = request.referrer
    if referrer:
        parsed = urllib.parse.urlsplit(referrer)
        if parsed.netloc == request.host and parsed.scheme in ('http', 'https'):
            return redirect(parsed.path + (f'?{parsed.query}' if parsed.query else ''))
    return redirect(url_for('index'))


# --- Transactional email delivery ---
def email_public_url(endpoint, **values):
    path = url_for(endpoint, **values)
    return f'{PUBLIC_BASE_URL}{path}' if PUBLIC_BASE_URL else url_for(endpoint, _external=True, **values)


def email_rate_limit(action, rate_key, limit, window_seconds):
    now = time.time()
    db = get_db()
    row = db.execute(
        'SELECT window_started, request_count FROM email_rate_limits WHERE action = ? AND rate_key = ?',
        (action, rate_key),
    ).fetchone()
    if not row or now - row['window_started'] >= window_seconds:
        db.execute(
            '''INSERT INTO email_rate_limits (action, rate_key, window_started, request_count)
               VALUES (?, ?, ?, 1)
               ON CONFLICT(action, rate_key) DO UPDATE SET window_started = excluded.window_started,
               request_count = excluded.request_count''',
            (action, rate_key, now),
        )
        db.commit()
        return True
    if row['request_count'] >= limit:
        return False
    db.execute(
        'UPDATE email_rate_limits SET request_count = request_count + 1 WHERE action = ? AND rate_key = ?',
        (action, rate_key),
    )
    db.commit()
    return True


def _record_email_message(provider, provider_message_id, recipient, subject, template_key, status='accepted'):
    db = get_db()
    db.execute(
        '''INSERT INTO email_messages
           (provider, provider_message_id, recipient, subject, template_key, status, sent_at, last_event_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(provider, provider_message_id) DO UPDATE SET status = excluded.status,
           last_event_at = excluded.last_event_at''',
        (provider, provider_message_id, recipient, subject, template_key, status, time.time(), time.time()),
    )
    db.commit()


def _send_resend_email(subject, recipient, html_body, text_body):
    payload = json.dumps({
        'from': RESEND_FROM_EMAIL,
        'to': [recipient],
        'subject': subject,
        'html': html_body,
        'text': text_body,
    }).encode('utf-8')
    req = urllib.request.Request(
        'https://api.resend.com/emails',
        data=payload,
        headers={'Authorization': f'Bearer {RESEND_API_KEY}', 'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as error:
        app.logger.error('Transactional email provider rejected a message: HTTP %s', error.code)
        raise RuntimeError('The email provider rejected the message.') from error
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        app.logger.error('Transactional email provider was unavailable.')
        raise RuntimeError('The email provider could not be reached.') from error
    message_id = data.get('id')
    if not message_id:
        raise RuntimeError('The email provider returned no message identifier.')
    return message_id


def _send_smtp_email(subject, recipient, html_body, text_body):
    smtp_server = os.getenv('MAIL_SERVER', '').strip()
    smtp_port = int(os.getenv('MAIL_PORT', '587'))
    smtp_user = os.getenv('MAIL_USERNAME', '').strip()
    smtp_password = os.getenv('MAIL_PASSWORD', '')
    sender = os.getenv('MAIL_DEFAULT_SENDER', '').strip() or smtp_user
    message = MIMEMultipart('alternative')
    message['From'] = sender
    message['To'] = recipient
    message['Subject'] = subject
    message.attach(MIMEText(text_body, 'plain', 'utf-8'))
    message.attach(MIMEText(html_body, 'html', 'utf-8'))
    try:
        if smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=15) as server:
                server.login(smtp_user, smtp_password)
                server.send_message(message)
        else:
            with smtplib.SMTP(smtp_server, smtp_port, timeout=15) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(smtp_user, smtp_password)
                server.send_message(message)
    except (OSError, smtplib.SMTPException) as error:
        app.logger.error('SMTP provider could not send a message.')
        raise RuntimeError('The email provider could not send the message.') from error
    return None


def send_email(subject, recipient, html_body, text_body=None, template_key=None):
    if not email_delivery_configured():
        raise RuntimeError('Transactional email delivery is not configured.')
    text_body = text_body or re.sub(r'<[^>]+>', ' ', html_body)
    if EMAIL_PROVIDER == 'resend':
        provider_message_id = _send_resend_email(subject, recipient, html_body, text_body)
    elif EMAIL_PROVIDER == 'smtp':
        provider_message_id = _send_smtp_email(subject, recipient, html_body, text_body)
    else:
        raise RuntimeError('Unsupported email provider configuration.')
    _record_email_message(EMAIL_PROVIDER, provider_message_id, recipient, subject, template_key)
    return provider_message_id


def verify_resend_webhook(raw_body, headers):
    if not RESEND_WEBHOOK_SECRET:
        return False
    svix_id = headers.get('svix-id', '')
    timestamp = headers.get('svix-timestamp', '')
    signatures = headers.get('svix-signature', '').split()
    try:
        timestamp_value = int(timestamp)
        if abs(time.time() - timestamp_value) > EMAIL_WEBHOOK_MAX_AGE_SECONDS:
            return False
    except (TypeError, ValueError):
        return False
    secret = RESEND_WEBHOOK_SECRET.removeprefix('whsec_')
    try:
        secret_bytes = base64.b64decode(secret)
    except (ValueError, base64.binascii.Error):
        return False
    signed_content = f'{svix_id}.{timestamp}.'.encode('utf-8') + raw_body
    expected = base64.b64encode(hmac.new(secret_bytes, signed_content, hashlib.sha256).digest()).decode('ascii')
    return any(
        signature.startswith('v1,') and hmac.compare_digest(signature[3:], expected)
        for signature in signatures
    )


@app.route('/webhooks/resend', methods=['POST'])
def resend_webhook():
    raw_body = request.get_data(cache=True)
    if not verify_resend_webhook(raw_body, request.headers):
        return jsonify({'error': 'Invalid webhook signature.'}), 401
    try:
        event = json.loads(raw_body.decode('utf-8'))
        event_type = event['type']
        data = event.get('data') or {}
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError):
        return jsonify({'error': 'Invalid webhook payload.'}), 400
    event_id = request.headers.get('svix-id', '')
    if not event_id:
        return jsonify({'error': 'Missing webhook event identifier.'}), 400
    db = get_db()
    try:
        db.execute(
            '''INSERT INTO email_webhook_events (provider, event_id, event_type, payload)
               VALUES ('resend', ?, ?, ?)''',
            (event_id, event_type, raw_body.decode('utf-8')),
        )
    except DB_INTEGRITY_ERRORS:
        db.rollback()
        return jsonify({'status': 'duplicate'}), 200

    event_column = {
        'email.sent': ('sent', 'sent_at'),
        'email.delivered': ('delivered', 'delivered_at'),
        'email.delivery_delayed': ('delayed', 'delayed_at'),
        'email.bounced': ('bounced', 'bounced_at'),
        'email.failed': ('failed', 'failed_at'),
        'email.suppressed': ('bounced', 'bounced_at'),
        'email.complained': ('complained', 'complained_at'),
    }.get(event_type)
    provider_message_id = data.get('email_id')
    if event_column and provider_message_id:
        status, timestamp_column = event_column
        reason = (data.get('bounce') or {}).get('message') or data.get('reason')
        db.execute(
            f'''UPDATE email_messages SET status = ?, {timestamp_column} = ?, last_event_at = ?,
                failure_reason = COALESCE(?, failure_reason)
                WHERE provider = 'resend' AND provider_message_id = ?''',
            (status, time.time(), time.time(), reason, provider_message_id),
        )
        if status == 'bounced':
            for address in data.get('to') or []:
                db.execute(
                    '''UPDATE users SET email_delivery_status = 'bounced',
                       email_delivery_last_event = ?, email_bounced_at = ?
                       WHERE LOWER(email) = LOWER(?)''',
                    (event_type, time.time(), address),
                )
    db.commit()
    return jsonify({'status': 'ok'}), 200


# --- Forgot / Reset Password ---
@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE LOWER(email) = ?', (email,)).fetchone()
        # Always show success to prevent user enumeration
        allowed = (
            email_rate_limit('password_reset_ip', request.remote_addr or 'unknown', 5, 3600)
            and email_rate_limit('password_reset_email', email or 'empty', 3, 3600)
        )
        if user and allowed and email_delivery_configured():
            token = secrets.token_urlsafe(32)
            expires = time.time() + PASSWORD_RESET_TTL_SECONDS
            db.execute(
                '''UPDATE users SET password_reset_token = NULL, password_reset_token_hash = ?,
                   password_reset_expires = ? WHERE id = ?''',
                (token_digest(token), expires, user['id']),
            )
            db.commit()
            reset_link = email_public_url('reset_password', token=token)
            try:
                html = render_template('emails/password_reset.html',
                                       user_name=user['full_name'],
                                       reset_link=reset_link)
                text = render_template('emails/password_reset.txt',
                                       user_name=user['full_name'],
                                       reset_link=reset_link)
                send_email('Reset your KwachaStay password', user['email'], html, text, 'password_reset')
            except RuntimeError:
                app.logger.error('Password reset delivery failed.')
        flash('If that email is registered, you will receive a reset link shortly.', 'info')
        return redirect(url_for('login'))
    return render_template('forgot_password.html')


@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    db = get_db()
    user = db.execute(
        '''SELECT * FROM users WHERE password_reset_token_hash = ?
           AND password_reset_expires > ?''',
        (token_digest(token), time.time()),
    ).fetchone()

    if not user:
        flash('This password reset link is invalid or has expired.', 'error')
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        if not check_rate_limit('reset_password_ip', client_ip(), 10, 900):
            abort(429, description='Too many password reset attempts. Please try again later.')
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')
        error = validate_password_strength(password)
        if not error and password != confirm:
            error = 'Passwords do not match.'

        if error:
            flash(error, 'error')
            return render_template('reset_password.html', token=token)

        db.execute(
            '''UPDATE users SET password = ?, password_reset_token = NULL,
               password_reset_token_hash = NULL, password_reset_expires = NULL,
               session_version = COALESCE(session_version, 1) + 1 WHERE id = ?''',
            (generate_password_hash(password), user['id'])
        )
        db.commit()
        session.clear()
        flash('Password reset successful! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('reset_password.html', token=token)


# --- Notifications ---
@app.route('/notifications')
@login_required
def notifications():
    db = get_db()
    notifs = db.execute(
        'SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC LIMIT 50',
        (g.user['id'],)
    ).fetchall()
    # Mark all as read
    db.execute('UPDATE notifications SET is_read = 1 WHERE user_id = ?', (g.user['id'],))
    db.commit()
    return render_template('notifications.html', notifications=notifs)


@app.route('/notifications/mark_read', methods=['POST'])
@login_required
def mark_notifications_read():
    db = get_db()
    db.execute('UPDATE notifications SET is_read = 1 WHERE user_id = ?', (g.user['id'],))
    db.commit()
    return jsonify({'status': 'ok'})


@app.route('/send_message', methods=['POST'])
@login_required
def send_message():
    if not check_rate_limit('send_message_user', str(g.user['id']), 20, 600):
        abort(429, description='Too many messages sent. Please wait a few minutes and try again.')
    receiver_raw = (request.form.get('receiver_id') or '').strip()
    property_raw = (request.form.get('property_id') or '').strip()
    content = (request.form.get('content') or '').strip()

    if not content or not receiver_raw:
        flash('Message content required.', 'error')
        return safe_redirect_referrer('dashboard')
    if len(content) > 2000:
        flash('Message must be 2,000 characters or fewer.', 'error')
        return safe_redirect_referrer('dashboard')
    try:
        receiver_id = int(receiver_raw)
        property_id = int(property_raw) if property_raw else None
    except ValueError:
        flash('Invalid recipient or property.', 'error')
        return safe_redirect_referrer('dashboard')
    if receiver_id == g.user['id']:
        flash('You cannot send a message to yourself.', 'error')
        return safe_redirect_referrer('dashboard')

    db = get_db()
    receiver = db.execute(
        "SELECT id, full_name FROM users WHERE id = ? AND role != 'banned'", (receiver_id,)
    ).fetchone()
    if not receiver:
        flash('Recipient not found.', 'error')
        return safe_redirect_referrer('dashboard')
    prop_info = None
    if property_id is not None:
        prop_info = db.execute(
            'SELECT id, title FROM properties WHERE id = ?', (property_id,)
        ).fetchone()
        if not prop_info:
            flash('Property not found.', 'error')
            return safe_redirect_referrer('dashboard')

    db.execute(
        'INSERT INTO messages (sender_id, receiver_id, property_id, content) VALUES (?, ?, ?, ?)',
        (g.user['id'], receiver_id, property_id, content),
    )
    db.commit()

    # Create an in-app notification for the recipient
    try:
        notif_msg = f"New message from {g.user['full_name']}"
        if prop_info:
            notif_msg += f" about '{prop_info['title']}'"
        create_notification(db, receiver_id, notif_msg, url_for('dashboard') + '#messages')
        db.commit()
    except Exception:
        app.logger.error('Could not create message notification for user %s.', receiver_id)

    flash('Message sent!', 'success')
    return safe_redirect_referrer('dashboard')

@app.route('/message/reply/<int:message_id>', methods=['POST'])
@login_required
def reply_message(message_id):
    if not check_rate_limit('send_message_user', str(g.user['id']), 20, 600):
        abort(429, description='Too many messages sent. Please wait a few minutes and try again.')
    db = get_db()
    original = db.execute('SELECT * FROM messages WHERE id = ?', (message_id,)).fetchone()
    if not original:
        flash('Original message not found.', 'error')
        return redirect(url_for('dashboard'))
    if g.user['id'] not in (original['sender_id'], original['receiver_id']):
        abort(403)

    content = request.form.get('content', '').strip()
    if not content:
        flash('Reply cannot be empty.', 'error')
        return redirect(url_for('dashboard'))
    if len(content) > 2000:
        flash('Reply must be 2,000 characters or fewer.', 'error')
        return redirect(url_for('dashboard'))

    # Reply goes back to the other participant in the original message
    receiver_id = original['sender_id'] if original['receiver_id'] == g.user['id'] else original['receiver_id']
    db.execute(
        'INSERT INTO messages (sender_id, receiver_id, property_id, content, parent_id) VALUES (?, ?, ?, ?, ?)',
        (g.user['id'], receiver_id, original['property_id'], content, message_id)
    )
    # Mark original as read only when the recipient replies
    if original['receiver_id'] == g.user['id']:
        db.execute('UPDATE messages SET is_read = 1 WHERE id = ?', (message_id,))
    db.commit()

    try:
        notif_msg = f"Reply from {g.user['full_name']}"
        create_notification(db, receiver_id, notif_msg, url_for('dashboard') + '#messages')
        db.commit()
    except Exception:
        app.logger.error('Could not create reply notification for user %s.', receiver_id)

    flash('Reply sent!', 'success')
    return redirect(url_for('dashboard'))


@app.route('/messages/mark_read', methods=['POST'])
@login_required
def mark_messages_read():
    db = get_db()
    db.execute('UPDATE messages SET is_read = 1 WHERE receiver_id = ?', (g.user['id'],))
    db.commit()
    return jsonify({'status': 'ok'})


@app.route('/profile/edit', methods=['POST'])
@login_required
def edit_profile():
    full_name = request.form.get('full_name', '').strip()
    phone_raw = request.form.get('phone', '').strip()
    profile_pic_raw = request.form.get('profile_pic', '').strip()
    country_region = request.form.get('country_region', 'ZM').upper()

    if not full_name or len(full_name) > 120:
        flash('Enter a valid name (up to 120 characters).', 'error')
        return redirect(url_for('dashboard'))
    try:
        phone = normalize_phone_number(phone_raw, country_region) if phone_raw else g.user['phone']
        profile_pic = validate_image_url(profile_pic_raw, allow_empty=True)
    except ValueError as error:
        flash(str(error), 'error')
        return redirect(url_for('dashboard'))

    db = get_db()
    phone_changed = phone != g.user['phone']
    if phone_changed:
        db.execute(
            '''UPDATE users SET full_name = ?, phone = ?, profile_pic = ?,
               phone_verified_at = NULL, phone_verification_token = NULL,
               phone_verification_expires = NULL, phone_verification_attempts = 0
               WHERE id = ?''',
            (full_name, phone, profile_pic or None, g.user['id']),
        )
    else:
        db.execute(
            'UPDATE users SET full_name = ?, phone = ?, profile_pic = ? WHERE id = ?',
            (full_name, phone, profile_pic or None, g.user['id']),
        )
    db.commit()
    flash('Profile updated successfully!', 'success')
    return redirect(url_for('dashboard'))


def send_twilio_verification_sms(phone, code):
    if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_FROM_NUMBER):
        raise RuntimeError('Phone verification is unavailable until the SMS provider is configured.')
    message = urllib.parse.urlencode({
        'From': TWILIO_FROM_NUMBER,
        'To': phone,
        'Body': f'Your KwachaStay verification code is {code}. It expires in 10 minutes.',
    }).encode('utf-8')
    credentials = base64.b64encode(
        f'{TWILIO_ACCOUNT_SID}:{TWILIO_AUTH_TOKEN}'.encode('utf-8')
    ).decode('ascii')
    req = urllib.request.Request(
        f'https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json',
        data=message,
        headers={
            'Authorization': f'Basic {credentials}',
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as error:
        app.logger.error('SMS provider rejected verification message: HTTP %s', error.code)
        raise RuntimeError('The SMS provider could not send a verification code. Try again later.') from error
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        app.logger.exception('Could not send phone verification SMS')
        raise RuntimeError('The SMS provider could not be reached. Try again later.') from error
    if not data.get('sid'):
        raise RuntimeError('The SMS provider did not confirm delivery of the verification message.')


@app.route('/profile/verify-email', methods=['POST'])
@login_required
def send_email_verification():
    if g.user['email_verified_at']:
        flash('Your email address is already verified.', 'info')
        return redirect(url_for('dashboard'))
    if not email_rate_limit('email_verification_user', str(g.user['id']), 3, 3600):
        flash('Please wait before requesting another verification email.', 'error')
        return redirect(url_for('dashboard'))
    token = secrets.token_urlsafe(32)
    expires = time.time() + EMAIL_VERIFICATION_TTL_SECONDS
    db = get_db()
    db.execute(
        '''UPDATE users SET email_verification_token = NULL,
           email_verification_token_hash = ?, email_verification_expires = ? WHERE id = ?''',
        (token_digest(token), expires, g.user['id']),
    )
    db.commit()
    verification_link = email_public_url('verify_email', token=token)
    try:
        html = render_template('emails/account_verification.html',
                               user_name=g.user['full_name'], verification_link=verification_link)
        text = render_template('emails/account_verification.txt',
                               user_name=g.user['full_name'], verification_link=verification_link)
        send_email('Verify your KwachaStay email', g.user['email'], html, text, 'account_verification')
    except RuntimeError:
        app.logger.error('Email verification delivery failed.')
        flash('Could not send the verification email. Please try again later.', 'error')
        return redirect(url_for('dashboard'))
    flash('A verification link was sent to your email address.', 'success')
    return redirect(url_for('dashboard'))


@app.route('/verify-email/<token>')
def verify_email(token):
    db = get_db()
    user = db.execute(
        '''SELECT id FROM users
           WHERE email_verification_token_hash = ?
           AND email_verification_expires > ?''',
        (token_digest(token), time.time()),
    ).fetchone()
    if not user:
        flash('This email verification link is invalid or has expired.', 'error')
        return redirect(url_for('login'))
    db.execute(
        '''UPDATE users SET email_verified_at = CURRENT_TIMESTAMP,
           email_verification_token = NULL, email_verification_token_hash = NULL,
           email_verification_expires = NULL
           WHERE id = ?''',
        (user['id'],),
    )
    db.commit()
    flash('Email verified successfully.', 'success')
    return redirect(url_for('login'))


@app.route('/profile/verify-phone', methods=['POST'])
@login_required
def send_phone_verification():
    phone_digits = re.sub(r'\D', '', g.user['phone'] or '')
    if phone_digits.startswith('260'):
        phone_digits = phone_digits[3:]
    if len(phone_digits) != 9 or not phone_digits.startswith(('7', '9')):
        flash('Update your profile with a valid Zambian mobile number before verification.', 'error')
        return redirect(url_for('dashboard'))
    if g.user['phone_verified_at']:
        flash('Your phone number is already verified.', 'info')
        return redirect(url_for('dashboard'))
    db = get_db()
    if (g.user['phone_verification_sent_at']
            and time.time() - g.user['phone_verification_sent_at'] < 60):
        flash('Please wait one minute before requesting another verification code.', 'error')
        return redirect(url_for('dashboard'))

    code = f'{secrets.randbelow(1_000_000):06d}'
    code_hash = hmac.new(
        app.secret_key.encode('utf-8'),
        f'{g.user["id"]}:{code}'.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()
    db.execute(
        '''UPDATE users SET phone_verification_token = ?,
           phone_verification_expires = ?, phone_verification_sent_at = ?,
           phone_verification_attempts = 0 WHERE id = ?''',
        (code_hash, time.time() + 600, time.time(), g.user['id']),
    )
    db.commit()
    try:
        send_twilio_verification_sms(f'+260{phone_digits}', code)
    except RuntimeError as error:
        db.execute(
            '''UPDATE users SET phone_verification_token = NULL,
               phone_verification_expires = NULL WHERE id = ?''',
            (g.user['id'],),
        )
        db.commit()
        flash(str(error), 'error')
        return redirect(url_for('dashboard'))
    flash('A phone verification code was sent. It expires in 10 minutes.', 'success')
    return redirect(url_for('dashboard'))


@app.route('/profile/verify-phone/confirm', methods=['POST'])
@login_required
def confirm_phone_verification():
    code = request.form.get('code', '').strip()
    if not re.fullmatch(r'\d{6}', code):
        flash('Enter the six-digit verification code.', 'error')
        return redirect(url_for('dashboard'))
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE id = ?', (g.user['id'],)).fetchone()
    if (not user['phone_verification_token']
            or not user['phone_verification_expires']
            or user['phone_verification_expires'] < time.time()
            or user['phone_verification_attempts'] >= 5):
        flash('The phone verification code has expired. Request a new one.', 'error')
        return redirect(url_for('dashboard'))
    candidate = hmac.new(
        app.secret_key.encode('utf-8'),
        f'{g.user["id"]}:{code}'.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(candidate, user['phone_verification_token']):
        attempts = user['phone_verification_attempts'] + 1
        db.execute(
            '''UPDATE users SET phone_verification_attempts = ?,
               phone_verification_token = CASE WHEN ? >= 5 THEN NULL ELSE phone_verification_token END,
               phone_verification_expires = CASE WHEN ? >= 5 THEN NULL ELSE phone_verification_expires END
               WHERE id = ?''',
            (attempts, attempts, attempts, g.user['id']),
        )
        db.commit()
        flash('That code is not correct. Request a new code after five unsuccessful attempts.', 'error')
        return redirect(url_for('dashboard'))
    db.execute(
        '''UPDATE users SET phone_verified_at = CURRENT_TIMESTAMP,
           phone_verification_token = NULL, phone_verification_expires = NULL,
           phone_verification_attempts = 0 WHERE id = ?''',
        (g.user['id'],),
    )
    db.commit()
    flash('Phone number verified successfully.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/checkout/<int:property_id>', methods=('GET', 'POST'))
@tenant_required
def checkout(property_id):
    db = get_db()
    expire_pending_booking_requests(db, force=True)
    property = db.execute(
        'SELECT * FROM properties WHERE id = ? AND is_active = 1',
        (property_id,),
    ).fetchone()
    if not property:
        flash('This listing is not available for booking.', 'error')
        return redirect(url_for('index'))
    if property['owner_id'] == g.user['id']:
        flash('You cannot book your own property.', 'error')
        return redirect(url_for('property_details', property_id=property_id))
    
    default_unit = 'month' if property['price_period'] == 'month' else 'night'
    can_book_hourly = supports_hourly_booking(property)
    effective_hourly_rate = get_effective_hourly_rate(property)
    upfront_months = get_upfront_months(property)
    requested_unit = (request.args.get('unit') or default_unit).strip().lower()
    initial_unit = 'hour' if (requested_unit == 'hour' and can_book_hourly) else default_unit
    initial_min = MIN_HOURLY_STAY_HOURS if initial_unit == 'hour' else (upfront_months if initial_unit == 'month' else 1)
    initial_max = MAX_HOURLY_STAY_HOURS if initial_unit == 'hour' else (60 if initial_unit == 'month' else 365)
    try:
        initial_duration = int(request.args.get('duration', str(initial_min)))
    except (TypeError, ValueError):
        initial_duration = initial_min
    if not initial_min <= initial_duration <= initial_max:
        initial_duration = initial_min

    checkout_ctx = {
        'property': property,
        'user': g.user,
        'initial_duration': initial_duration,
        'initial_unit': initial_unit,
        'can_book_hourly': can_book_hourly,
        'effective_hourly_rate': effective_hourly_rate,
        'upfront_months': upfront_months,
        'min_hourly_stay': MIN_HOURLY_STAY_HOURS,
    }

    if request.method == 'POST':
        if not check_rate_limit('checkout_user', str(g.user['id']), 10, 900):
            abort(429, description='Too many booking requests submitted. Please wait a few minutes and try again.')
        tenant_name = request.form.get('tenant_name', '').strip()
        tenant_phone = request.form.get('tenant_phone', '').strip()
        if request.form.get('accept_policies') != 'on':
            flash('Please review and accept the house rules and cancellation policy.', 'error')
            return render_template('checkout.html', **checkout_ctx)
        check_in = parse_iso_date(request.form.get('check_in'))
        submitted_unit = (request.form.get('duration_unit') or default_unit).strip().lower()
        duration_unit = 'hour' if (submitted_unit == 'hour' and can_book_hourly) else default_unit
        duration_value = request.form.get('duration_val', '')
        try:
            duration = int(duration_value)
        except (TypeError, ValueError):
            duration = 0

        if not tenant_name or not tenant_phone:
            flash('Name and phone number are required.', 'error')
            return render_template('checkout.html', **checkout_ctx)
        if not check_in or check_in < date.today():
            flash('Choose a valid future check-in date.', 'error')
            return render_template('checkout.html', **checkout_ctx)
        if duration_unit == 'hour':
            if duration < MIN_HOURLY_STAY_HOURS or duration > MAX_HOURLY_STAY_HOURS:
                flash(f'Hourly bookings require between {MIN_HOURLY_STAY_HOURS} and {MAX_HOURLY_STAY_HOURS} hours.', 'error')
                return render_template('checkout.html', **checkout_ctx)
        else:
            max_duration = 60 if duration_unit == 'month' else 365
            min_duration = upfront_months if duration_unit == 'month' else 1
            if duration < min_duration or duration > max_duration:
                if duration_unit == 'month' and min_duration > 1:
                    flash(f'This property requires at least {min_duration} months upfront (up to {max_duration} months).', 'error')
                else:
                    flash(f'Duration must be between {min_duration} and {max_duration} {duration_unit}(s).', 'error')
                return render_template('checkout.html', **checkout_ctx)

        try:
            quote = quote_property_stay(
                db, property, check_in, duration,
                duration_unit_override=('hour' if duration_unit == 'hour' else None),
            )
        except ValueError as error:
            flash(str(error), 'error')
            return render_template('checkout.html', **checkout_ctx)
        check_out = quote['check_out']
        base_amount = quote['base_amount']
        cleaning_fee = quote['cleaning_fee']
        refundable_deposit = quote['refundable_deposit']
        total_price = quote['total_price']

        try:
            db.execute('BEGIN IMMEDIATE')
            conflict = booking_conflict(db, property_id, check_in, check_out)
            if conflict:
                db.rollback()
                flash(conflict, 'error')
                return render_template('checkout.html', **checkout_ctx)

            tx_ref = f'KS-{secrets.token_urlsafe(12)}'
            db.execute(
                '''INSERT INTO bookings (
                    property_id, user_id, tenant_name, tenant_phone, check_in, check_out,
                    total_price, base_amount, service_fee, cleaning_fee, refundable_deposit,
                    payment_status, payment_method, duration, duration_unit,
                    tx_ref, booking_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, 'pending')''',
                (property_id, g.user['id'], tenant_name, tenant_phone, check_in.isoformat(),
                 check_out.isoformat(), total_price, base_amount, quote['service_fee'],
                 cleaning_fee, refundable_deposit,
                 request.form.get('payment_method', '').strip(), duration, duration_unit, tx_ref),
            )
            db.commit()
        except DB_ERRORS:
            db.rollback()
            app.logger.exception('Could not create booking request for property %s', property_id)
            flash('We could not submit your booking request. Please try again.', 'error')
            return render_template('checkout.html', **checkout_ctx)

        flash(f'Booking request sent for {property["title"]}. No payment has been taken.', 'success')
        
        # Send Email to Owner
        try:
            owner = db.execute('SELECT email, full_name FROM users WHERE id = ?', (property['owner_id'],)).fetchone()
            if owner:
                html_body = render_template('emails/booking_notification.html', 
                                           owner_name=owner['full_name'],
                                           property_title=property['title'],
                                           tenant_name=tenant_name,
                                           check_in=check_in,
                                           check_out=check_out.isoformat(),
                                           duration=duration,
                                           duration_unit=duration_unit,
                                           total_price=total_price)
                send_email(f"New Booking Request: {property['title']}", owner['email'], html_body,
                           render_template('emails/booking_notification.txt', owner_name=owner['full_name'],
                                           property_title=property['title'], tenant_name=tenant_name,
                                           check_in=check_in, check_out=check_out.isoformat(),
                                           duration=duration, duration_unit=duration_unit, total_price=total_price),
                           'booking_notification')
        except Exception:
            app.logger.error('Owner booking email delivery failed.')
        
        # Send request acknowledgement, not a payment or booking confirmation.
        try:
            tenant_html = render_template('emails/booking_confirmation.html',
                                         tenant_name=g.user['full_name'],
                                         property_title=property['title'],
                                         owner_name=owner['full_name'] if owner else 'Host',
                                         check_in=check_in.isoformat(),
                                         check_out=check_out.isoformat(),
                                         tx_ref=tx_ref)
            send_email(f"Booking Request Received: {property['title']}", g.user['email'], tenant_html,
                       render_template('emails/booking_confirmation.txt', tenant_name=g.user['full_name'],
                                       property_title=property['title'],
                                       owner_name=owner['full_name'] if owner else 'Host',
                                       check_in=check_in.isoformat(), check_out=check_out.isoformat(), tx_ref=tx_ref),
                       'booking_confirmation')
        except Exception:
            app.logger.error('Tenant booking email delivery failed.')

        return redirect(url_for('dashboard'))

    return render_template('checkout.html', **checkout_ctx)



# --- Image Upload Route ---
@app.route('/upload_image', methods=['POST'])
@landlord_required
def upload_image():
    if not check_rate_limit('upload_image_user', str(g.user['id']), 30, 600):
        return jsonify({'error': 'Upload rate limit exceeded. Please wait a few minutes.'}), 429
    if not app.config['UPLOADS_ENABLED']:
        return jsonify({'error': 'Photo uploads are disabled until durable production storage is configured.'}), 503
    if 'image' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    try:
        canonical_ext, canonical_mime = validate_image_upload(file)
    except ValueError as error:
        return jsonify({'error': str(error)}), 400
    filename = f"{uuid.uuid4().hex}.{canonical_ext}"
    try:
        stored_path = upload_storage.save(file, filename, content_type=canonical_mime)
    except (RuntimeError, ValueError, OSError):
        app.logger.exception('Image upload failed.')
        return jsonify({'error': 'Could not store the uploaded image. Please try again.'}), 502
    url = (
        stored_path if STORAGE_BACKEND == 'supabase'
        else url_for('static', filename=f'uploads/{filename}')
    )
    return jsonify({'url': url})


@app.route('/booking/<int:booking_id>/pay/mobile-money', methods=['POST'])
@tenant_required
def start_mobile_money_payment(booking_id):
    db = get_db()
    booking = db.execute(
        '''SELECT b.*, p.title
           FROM bookings b JOIN properties p ON p.id = b.property_id
           WHERE b.id = ? AND b.user_id = ?''',
        (booking_id, g.user['id']),
    ).fetchone()
    if not booking:
        flash('Booking not found or unauthorized.', 'error')
        return redirect(url_for('dashboard'))
    if booking['booking_status'] != 'confirmed':
        flash('The host must confirm this booking before you can pay.', 'error')
        return redirect(url_for('dashboard'))
    if booking['payment_status'] == 'paid':
        flash('This booking is already marked as paid.', 'info')
        return redirect(url_for('booking_receipt', booking_id=booking_id))
    if not flutterwave_checkout_enabled():
        flash('Mobile-money checkout needs Flutterwave credentials and the public HTTPS site URL configured. Please contact support.', 'error')
        return redirect(url_for('support_center', booking_id=booking_id))

    try:
        db.execute('BEGIN IMMEDIATE')
        current = db.execute(
            '''SELECT payment_status, booking_status FROM bookings
               WHERE id = ? AND user_id = ?''',
            (booking_id, g.user['id']),
        ).fetchone()
        if not current or current['booking_status'] != 'confirmed' or current['payment_status'] == 'paid':
            db.rollback()
            flash('This booking is no longer available for payment.', 'error')
            return redirect(url_for('dashboard'))
        previous = db.execute(
            '''SELECT checkout_url FROM payment_attempts
               WHERE booking_id = ? AND provider = 'flutterwave'
                 AND status = 'pending' AND checkout_url IS NOT NULL
               ORDER BY created_at DESC LIMIT 1''',
            (booking_id,),
        ).fetchone()
        if previous:
            db.rollback()
            return redirect(previous['checkout_url'])
        tx_ref = f'KS-MM-{secrets.token_urlsafe(16)}'
        db.execute(
            '''INSERT INTO payment_attempts (booking_id, tx_ref, provider, status)
               VALUES (?, ?, 'flutterwave', 'pending')''',
            (booking_id, tx_ref),
        )
        db.commit()
    except DB_ERRORS:
        db.rollback()
        app.logger.exception('Could not start mobile-money payment for booking %s', booking_id)
        flash('Could not start mobile-money checkout. Please try again.', 'error')
        return redirect(url_for('booking_receipt', booking_id=booking_id))

    try:
        response = flutterwave_api_request('POST', 'payments', {
            'tx_ref': tx_ref,
            'amount': booking['total_price'],
            'currency': 'ZMW',
            'redirect_url': f'{PUBLIC_BASE_URL}{url_for("flutterwave_payment_callback")}',
            'payment_options': 'mobilemoneyzambia',
            'customer': {
                'email': g.user['email'],
                'name': g.user['full_name'],
                'phonenumber': booking['tenant_phone'],
            },
            'customizations': {
                'title': 'KwachaStay',
                'description': f'Booking #{booking_id}: {booking["title"]}',
            },
        })
        checkout_url = (response.get('data') or {}).get('link')
        parsed_url = urllib.parse.urlparse(checkout_url or '')
        if (parsed_url.scheme != 'https' or parsed_url.hostname != 'checkout.flutterwave.com'
                or not checkout_url or len(checkout_url) > 2000):
            raise RuntimeError('Flutterwave returned an invalid secure checkout link.')
        db.execute(
            '''UPDATE payment_attempts
               SET checkout_url = ?, updated_at = CURRENT_TIMESTAMP
               WHERE tx_ref = ? AND status = 'pending' ''',
            (checkout_url, tx_ref),
        )
        db.commit()
        return redirect(checkout_url)
    except (RuntimeError,) + DB_ERRORS:
        db.rollback()
        db.execute(
            '''UPDATE payment_attempts SET status = 'failed', updated_at = CURRENT_TIMESTAMP
               WHERE tx_ref = ? AND status = 'pending' ''',
            (tx_ref,),
        )
        db.commit()
        app.logger.exception('Could not initialize Flutterwave checkout for booking %s', booking_id)
        flash('Mobile-money checkout could not be started. Please try again or contact support.', 'error')
        return redirect(url_for('booking_receipt', booking_id=booking_id))


@app.route('/booking/<int:booking_id>/pay/bank-transfer', methods=['GET', 'POST'])
@tenant_required
def bank_transfer_payment(booking_id):
    if not BANK_TRANSFER_ENABLED:
        flash('Bank transfer payment is not configured. Please contact support.', 'error')
        return redirect(url_for('booking_receipt', booking_id=booking_id))

    db = get_db()
    booking = db.execute(
        '''SELECT b.*, p.title, p.compound, p.image_main
           FROM bookings b
           JOIN properties p ON p.id = b.property_id
           WHERE b.id = ? AND b.user_id = ?''',
        (booking_id, g.user['id']),
    ).fetchone()
    if not booking:
        flash('Booking not found or unauthorized.', 'error')
        return redirect(url_for('dashboard'))
    if booking['booking_status'] != 'confirmed':
        flash('The host must confirm this booking before payment.', 'error')
        return redirect(url_for('booking_receipt', booking_id=booking_id))
    if booking['payment_status'] == 'paid':
        flash('This booking is already marked as paid.', 'info')
        return redirect(url_for('booking_receipt', booking_id=booking_id))

    if request.method == 'POST':
        reference = request.form.get('transfer_reference', '').strip()
        if not re.fullmatch(r'[A-Za-z0-9._/-]{3,100}', reference):
            flash('Enter the bank transaction reference (3-100 letters, numbers, or . _ / -).', 'error')
            return render_template(
                'bank_transfer.html', booking=booking,
                bank_transfer_details=BANK_TRANSFER_DETAILS,
            )
        try:
            db.execute('BEGIN IMMEDIATE')
            result = db.execute(
                '''UPDATE bookings SET payment_method = 'Bank Transfer',
                   payment_claim_reference = ?, payment_claim_submitted_at = CURRENT_TIMESTAMP
                   WHERE id = ? AND user_id = ? AND booking_status = 'confirmed'
                     AND payment_status = 'pending' ''',
                (reference, booking_id, g.user['id']),
            )
            if result.rowcount != 1:
                db.rollback()
                flash('Booking payment status changed. Refresh the receipt and try again.', 'error')
                return redirect(url_for('booking_receipt', booking_id=booking_id))
            db.commit()
        except DB_ERRORS:
            db.rollback()
            app.logger.exception('Could not record bank transfer claim for booking %s', booking_id)
            flash('Could not submit the bank transfer reference. Please try again.', 'error')
            return redirect(url_for('booking_receipt', booking_id=booking_id))
        flash('Transfer reference submitted. Payment remains pending until KwachaStay verifies it with the bank.', 'success')
        return redirect(url_for('booking_receipt', booking_id=booking_id))

    return render_template(
        'bank_transfer.html', booking=booking,
        bank_transfer_details=BANK_TRANSFER_DETAILS,
    )


@app.route('/payment/flutterwave/callback')
def flutterwave_payment_callback():
    db = get_db()
    tx_ref = request.args.get('tx_ref', '').strip()
    transaction_id = request.args.get('transaction_id', '').strip()
    attempt = db.execute(
        '''SELECT pa.booking_id, b.user_id
           FROM payment_attempts pa
           JOIN bookings b ON b.id = pa.booking_id
           WHERE pa.tx_ref = ? AND pa.provider = 'flutterwave' ''',
        (tx_ref,),
    ).fetchone()
    if not attempt or not transaction_id.isdigit():
        flash('Payment was not verified. Check the booking receipt for its current status.', 'error')
        return redirect(url_for('dashboard') if g.user else url_for('login'))
    if g.user and attempt['user_id'] != g.user['id']:
        flash('That payment belongs to a different account.', 'error')
        return redirect(url_for('dashboard'))

    try:
        booking_id = record_flutterwave_payment(db, tx_ref, transaction_id)
        flash('Mobile-money payment verified. Your receipt has been updated.', 'success')
    except (RuntimeError, ValueError) + DB_ERRORS:
        db.rollback()
        app.logger.exception('Could not verify Flutterwave payment for booking %s', attempt['booking_id'])
        flash('We could not verify this payment yet. No paid status was recorded; please contact support.', 'error')
        return redirect(url_for('booking_receipt', booking_id=attempt['booking_id'])
                        if g.user else url_for('login'))
    return redirect(url_for('booking_receipt', booking_id=booking_id)
                    if g.user else url_for('login'))


@app.route('/webhooks/flutterwave', methods=['POST'])
def flutterwave_webhook():
    if not FLUTTERWAVE_SECRET_HASH:
        return jsonify({'error': 'Flutterwave webhook is not configured.'}), 503
    supplied_hash = request.headers.get('verif-hash', '')
    if not hmac.compare_digest(supplied_hash, FLUTTERWAVE_SECRET_HASH):
        return jsonify({'error': 'Invalid webhook signature.'}), 401
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or not isinstance(payload.get('data'), dict):
        return jsonify({'error': 'Invalid webhook payload.'}), 400
    if payload.get('event') != 'charge.completed':
        return jsonify({'status': 'ignored'}), 200
    transaction = payload['data']
    if str(transaction.get('status', '')).lower() != 'successful':
        return jsonify({'status': 'ignored'}), 200
    tx_ref = str(transaction.get('tx_ref') or '').strip()
    transaction_id = str(transaction.get('id') or '').strip()
    if not tx_ref or not transaction_id.isdigit():
        return jsonify({'error': 'Missing payment reference.'}), 400
    try:
        record_flutterwave_payment(get_db(), tx_ref, transaction_id)
    except ValueError:
        app.logger.warning('Ignoring Flutterwave webhook for unknown or invalid payment reference %s', tx_ref)
        return jsonify({'error': 'Payment reference not found or invalid.'}), 404
    except (RuntimeError,) + DB_ERRORS:
        get_db().rollback()
        app.logger.exception('Could not process Flutterwave payment webhook for reference %s', tx_ref)
        return jsonify({'error': 'Payment verification is temporarily unavailable.'}), 503
    return jsonify({'status': 'verified'}), 200


# --- Booking Approval Routes ---
@app.route('/booking/approve/<int:booking_id>', methods=['POST'])
@landlord_required
def approve_booking(booking_id):
    db = get_db()
    expire_pending_booking_requests(db, force=True)
    # Verify the booking belongs to one of the host's properties
    booking = db.execute('''
        SELECT b.*, p.title, p.owner_id, u.email as tenant_email, u.full_name as tenant_fullname
        FROM bookings b
        JOIN properties p ON b.property_id = p.id
        LEFT JOIN users u ON b.user_id = u.id
        WHERE b.id = ?
    ''', (booking_id,)).fetchone()

    if not booking or booking['owner_id'] != g.user['id']:
        flash('Unauthorized.', 'error')
        return redirect(url_for('dashboard'))

    if booking['booking_status'] != 'pending':
        flash('This booking request is no longer pending.', 'error')
        return redirect(url_for('dashboard'))

    check_in = parse_iso_date(booking['check_in'])
    check_out = parse_iso_date(booking['check_out'])
    if not check_in or not check_out:
        flash('This booking has invalid dates and cannot be approved.', 'error')
        return redirect(url_for('dashboard'))

    try:
        db.execute('BEGIN IMMEDIATE')
        conflict = booking_conflict(db, booking['property_id'], check_in, check_out, booking_id)
        if conflict:
            db.rollback()
            flash(f'Cannot approve this booking: {conflict}', 'error')
            return redirect(url_for('dashboard'))
        updated = db.execute(
            "UPDATE bookings SET booking_status = 'confirmed' WHERE id = ? AND booking_status = 'pending'",
            (booking_id,),
        )
        if updated.rowcount != 1:
            db.rollback()
            flash('This booking request has already been updated.', 'error')
            return redirect(url_for('dashboard'))
        db.commit()
    except DB_ERRORS:
        db.rollback()
        app.logger.exception('Could not approve booking %s', booking_id)
        flash('Could not approve this booking. Please try again.', 'error')
        return redirect(url_for('dashboard'))
    flash(f'Booking for "{booking["title"]}" has been confirmed!', 'success')

    # In-app notification for tenant
    try:
        if booking['user_id']:
            create_notification(db, booking['user_id'],
                f"Your booking for '{booking['title']}' has been confirmed!",
                url_for('dashboard'))
            db.commit()
    except Exception:
        app.logger.error('Could not create booking cancellation notification for booking %s.', booking_id)

    # Notify tenant by email
    try:
        if booking['tenant_email']:
            html = render_template('emails/booking_status.html',
                tenant_name=booking['tenant_fullname'] or booking['tenant_name'],
                property_title=booking['title'],
                status='confirmed',
                check_in=booking['check_in'],
                check_out=booking['check_out'],
                dashboard_url=email_public_url('dashboard'))
            send_email(f'Booking Confirmed: {booking["title"]}', booking['tenant_email'], html,
                       render_template('emails/booking_status.txt', tenant_name=booking['tenant_fullname'] or booking['tenant_name'],
                                       property_title=booking['title'], status='confirmed',
                                       check_in=booking['check_in'], check_out=booking['check_out']),
                       'booking_status')
    except Exception:
        app.logger.error('Booking status email delivery failed.')

    return redirect(url_for('dashboard'))


@app.route('/booking/decline/<int:booking_id>', methods=['POST'])
@landlord_required
def decline_booking(booking_id):
    db = get_db()
    expire_pending_booking_requests(db, force=True)
    booking = db.execute('''
        SELECT b.*, p.title, p.owner_id, u.email as tenant_email, u.full_name as tenant_fullname
        FROM bookings b
        JOIN properties p ON b.property_id = p.id
        LEFT JOIN users u ON b.user_id = u.id
        WHERE b.id = ?
    ''', (booking_id,)).fetchone()

    if not booking or booking['owner_id'] != g.user['id']:
        flash('Unauthorized.', 'error')
        return redirect(url_for('dashboard'))

    if booking['booking_status'] != 'pending':
        flash('Only pending booking requests can be declined.', 'error')
        return redirect(url_for('dashboard'))

    refund_update = ", refund_status = 'requested'" if booking['payment_status'] == 'paid' else ''
    db.execute(
        f"UPDATE bookings SET booking_status = 'declined'{refund_update} WHERE id = ?",
        (booking_id,),
    )
    db.commit()
    flash(f'Booking declined.', 'info')

    # In-app notification for tenant
    try:
        if booking['user_id']:
            create_notification(db, booking['user_id'],
                f"Unfortunately, your booking request for '{booking['title']}' was declined.",
                url_for('dashboard'))
            db.commit()
    except Exception:
        app.logger.error('Could not create booking cancellation notification for booking %s.', booking_id)

    # Notify tenant
    try:
        if booking['tenant_email']:
            html = render_template('emails/booking_status.html',
                tenant_name=booking['tenant_fullname'] or booking['tenant_name'],
                property_title=booking['title'],
                status='declined',
                check_in=booking['check_in'],
                check_out=booking['check_out'],
                dashboard_url=email_public_url('dashboard'))
            send_email(f'Booking Update: {booking["title"]}', booking['tenant_email'], html,
                       render_template('emails/booking_status.txt', tenant_name=booking['tenant_fullname'] or booking['tenant_name'],
                                       property_title=booking['title'], status='declined',
                                       check_in=booking['check_in'], check_out=booking['check_out']),
                       'booking_status')
    except Exception:
        app.logger.error('Booking status email delivery failed.')

    return redirect(url_for('dashboard'))


# --- Edit Property ---
@app.route('/property/<int:property_id>/edit', methods=['GET', 'POST'])
@landlord_required
def edit_property(property_id):
    db = get_db()
    property = db.execute('SELECT * FROM properties WHERE id = ? AND owner_id = ?',
                          (property_id, g.user['id'])).fetchone()
    if not property:
        flash('Property not found or unauthorized.', 'error')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        previous_price = float(property['price_per_night'])
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        price_raw = request.form.get('price', '').strip()
        compound = request.form.get('compound', '').strip()
        property_type = request.form.get('property_type', '').strip()
        price_period_raw = request.form.get('price_period', '').strip().lower()
        price_period = price_period_raw if price_period_raw in ('night', 'month') else default_price_period_for_type(property_type)
        if not title or not description or not compound or not property_type:
            flash('Please fill in all required property details.', 'error')
            return redirect(url_for('edit_property', property_id=property_id))
        if len(title) > 160 or len(description) > 5000:
            flash('Title must be under 160 characters and description under 5,000 characters.', 'error')
            return redirect(url_for('edit_property', property_id=property_id))
        try:
            price = parse_nonnegative_money(price_raw, 'Price')
            if price <= 0:
                raise ValueError('Price must be greater than zero.')
        except ValueError as error:
            flash(str(error), 'error')
            return redirect(url_for('edit_property', property_id=property_id))
        try:
            latitude, longitude = parse_location_coordinates(
                request.form.get('latitude'), request.form.get('longitude')
            )
            utility_fields = parse_property_utility_fields(request.form)
            checkin_fields = parse_checkin_fields(request.form, is_long_term=(price_period == 'month'))
            stay_terms = parse_stay_terms_fields(request.form, property_type, price_period)
        except ValueError as error:
            flash(str(error), 'error')
            return redirect(url_for('edit_property', property_id=property_id))
        cancellation_policy = request.form.get('cancellation_policy', 'moderate')
        house_rules = request.form.get('house_rules', '').strip()
        arrival_instructions = request.form.get('arrival_instructions', '').strip()
        arrival_directions = request.form.get('arrival_directions', '').strip()
        nearby_essentials = request.form.get('nearby_essentials', '').strip()
        main_photo_category = request.form.get('main_photo_category', 'other')
        try:
            cleaning_fee = parse_nonnegative_money(request.form.get('cleaning_fee'), 'Cleaning fee')
            refundable_deposit = parse_nonnegative_money(request.form.get('refundable_deposit'), 'Refundable deposit')
        except ValueError as error:
            flash(str(error), 'error')
            return redirect(url_for('edit_property', property_id=property_id))
        if (cancellation_policy not in ('flexible', 'moderate', 'strict')
                or len(house_rules) > 2000 or len(arrival_instructions) > 3000
                or len(arrival_directions) > 1000 or len(nearby_essentials) > 1000
                or main_photo_category not in PHOTO_CATEGORIES):
            flash('Choose a valid cancellation policy and keep house rules under 2,000 characters.', 'error')
            return redirect(url_for('edit_property', property_id=property_id))
        bed_type = request.form.get('bed_type')
        room_capacity = request.form.get('room_capacity')
        kitchen_type = request.form.get('kitchen_type')

        has_sitting_room = 1 if 'has_sitting_room' in request.form else 0
        has_solar    = 1 if 'has_solar'    in request.form else 0
        has_borehole = 1 if 'has_borehole' in request.form else 0
        has_pool     = 1 if 'has_pool'     in request.form else 0
        has_garden   = 1 if 'has_garden'   in request.form else 0
        has_bbq      = 1 if 'has_bbq'      in request.form else 0
        has_balcony  = 1 if 'has_balcony'  in request.form else 0
        has_ac       = 1 if 'has_ac'       in request.form else 0
        has_wifi     = 1 if 'has_wifi'     in request.form else 0
        has_parking  = 1 if 'has_parking'  in request.form else 0

        # Handle main image: new upload takes priority, then existing URL, then keep old
        new_main_image_raw = request.form.get('new_main_image_url', '').strip()
        extra_images_raw = request.form.get('extra_images', '').strip()
        try:
            new_main_image = validate_image_url(new_main_image_raw, allow_empty=True)
            validated_extra_images = []
            if extra_images_raw:
                for img in extra_images_raw.split(','):
                    img = img.strip()
                    if img:
                        validated_extra_images.append(validate_image_url(img))
        except ValueError as error:
            flash(str(error), 'error')
            return redirect(url_for('edit_property', property_id=property_id))
        image_main = new_main_image if new_main_image else property['image_main']

        db.execute('''
            UPDATE properties SET
                title=?, description=?, price_per_night=?, price_period=?, compound=?,
                property_type=?, bed_type=?, room_sharing=?, room_capacity=?, kitchen_type=?,
                has_sitting_room=?, upfront_months=?, hourly_rate=?, has_solar=?, has_borehole=?, has_pool=?,
                has_garden=?, has_bbq=?, has_balcony=?, has_ac=?, has_wifi=?,
                has_parking=?, image_main=?, cancellation_policy=?, house_rules=?,
                cleaning_fee=?, refundable_deposit=?, utilities_included=?,
                power_backup=?, water_supply=?, internet_availability=?,
                internet_speed_mbps=?, emergency_contact_name=?, emergency_contact_phone=?,
                arrival_instructions=?, arrival_directions=?, nearby_essentials=?,
                checkin_time=?, checkout_time=?, self_checkin_method=?,
                main_photo_category=?, latitude=?, longitude=?
            WHERE id=? AND owner_id=?
        ''', (title, description, price, price_period, compound, property_type,
              bed_type, stay_terms['room_sharing'], room_capacity, kitchen_type, has_sitting_room,
              stay_terms['upfront_months'], stay_terms['hourly_rate'],
              has_solar, has_borehole, has_pool, has_garden, has_bbq,
              has_balcony, has_ac, has_wifi, has_parking, image_main,
              cancellation_policy, house_rules, cleaning_fee, refundable_deposit,
              1 if request.form.get('utilities_included') == 'on' else 0,
              utility_fields['power_backup'], utility_fields['water_supply'],
              utility_fields['internet_availability'], utility_fields['internet_speed_mbps'],
              utility_fields['emergency_contact_name'], utility_fields['emergency_contact_phone'],
              arrival_instructions, arrival_directions, nearby_essentials,
              checkin_fields['checkin_time'], checkin_fields['checkout_time'],
              checkin_fields['self_checkin_method'], main_photo_category,
              latitude, longitude,
              property_id, g.user['id']))

        updated_property = db.execute(
            'SELECT * FROM properties WHERE id = ?', (property_id,)
        ).fetchone()
        if (property['is_active']
                and float(updated_property['price_per_night']) != previous_price):
            notify_matching_searches(
                db, updated_property, event='price', previous_price=previous_price
            )

        # Handle extra images if provided
        extra_image_category = request.form.get('extra_image_category', 'other')
        if extra_image_category not in PHOTO_CATEGORIES:
            extra_image_category = 'other'
        if validated_extra_images:
            # Add new images (don't delete existing to be safe)
            for img in validated_extra_images:
                try:
                    db.execute(
                        'INSERT INTO property_images (property_id, image_url, category) VALUES (?, ?, ?)',
                        (property_id, img, extra_image_category),
                    )
                except DB_ERRORS:
                    app.logger.exception('Could not add gallery photo to property %s', property_id)

        db.commit()
        flash('Property updated successfully!', 'success')
        return redirect(url_for('property_details', property_id=property_id))

    # Fetch existing extra images
    extra_images = db.execute('SELECT image_url, category FROM property_images WHERE property_id = ?',
                              (property_id,)).fetchall()
    photo_categories_present = {row['category'] for row in extra_images if row['category']}
    if property['image_main']:
        photo_categories_present.add(property['main_photo_category'] or 'other')
    return render_template(
        'edit_house.html',
        property=property,
        extra_images=extra_images,
        photo_categories_present=photo_categories_present,
        compounds=LUSAKA_NEIGHBOURHOODS,
        neighbourhood_coords=LUSAKA_NEIGHBOURHOOD_COORDS,
        photo_categories=PHOTO_CATEGORIES,
        power_backup_options=POWER_BACKUP_OPTIONS,
        water_supply_options=WATER_SUPPLY_OPTIONS,
        internet_options=INTERNET_OPTIONS,
    )


@app.route('/host/<int:user_id>')
def host_profile(user_id):
    db = get_db()
    host = db.execute(
        '''SELECT id, full_name, profile_pic, created_at, host_verification_status
           FROM users WHERE id = ?''',
        (user_id,),
    ).fetchone()
    if not host:
        flash('Host not found.', 'error')
        return redirect(url_for('index'))
    
    # Get host's active listings
    listings_raw = db.execute(
        '''SELECT p.*, u.full_name as owner_name,
                  u.email_verified_at as owner_email_verified_at FROM properties p
           JOIN users u ON p.owner_id = u.id
           WHERE p.owner_id = ? AND p.is_active = 1 ORDER BY p.created_at DESC''',
        (user_id,)
    ).fetchall()
    
    listings = []
    for prop in listings_raw:
        prop_dict = dict(prop)
        stats = db.execute("SELECT AVG(rating) as avg_rating, COUNT(id) as count FROM reviews WHERE property_id = ?", (prop['id'],)).fetchone()
        prop_dict['rating'] = round(stats['avg_rating'], 1) if stats['avg_rating'] else None
        prop_dict['review_count'] = stats['count']
        listings.append(prop_dict)
    
    # Total reviews on all host properties
    total_reviews = db.execute(
        '''SELECT COUNT(*) FROM reviews r
           JOIN properties p ON r.property_id = p.id
           WHERE p.owner_id = ?''', (user_id,)
    ).fetchone()[0]
    
    return render_template(
        'host_profile.html',
        host=host,
        listings=listings,
        total_reviews=total_reviews,
        host_response_stats=get_host_response_stats(db, user_id),
        host_reliability_stats=get_host_reliability_stats(db, user_id),
    )


# --- Change Password ---
@app.route('/profile/change_password', methods=['POST'])
@login_required
def change_password():
    if not check_rate_limit('change_password_user', str(g.user['id']), 10, 900):
        abort(429, description='Too many password change attempts. Please wait and try again.')
    current = request.form.get('current_password', '')
    new_pw = request.form.get('new_password', '')
    confirm = request.form.get('confirm_password', '')

    if not check_password_hash(g.user['password'], current):
        flash('Current password is incorrect.', 'error')
        return redirect(url_for('dashboard'))
    password_error = validate_password_strength(new_pw)
    if password_error:
        flash(password_error, 'error')
        return redirect(url_for('dashboard'))
    if new_pw != confirm:
        flash('Passwords do not match.', 'error')
        return redirect(url_for('dashboard'))

    db = get_db()
    user_id = g.user['id']
    new_sv = _user_session_version(g.user) + 1
    db.execute(
        'UPDATE users SET password = ?, session_version = ? WHERE id = ?',
        (generate_password_hash(new_pw), new_sv, user_id),
    )
    db.commit()
    # Regenerate session state and invalidate all other active devices
    was_permanent = session.permanent
    session.clear()
    now = time.time()
    session['user_id'] = user_id
    session['session_version'] = new_sv
    session['_session_created_at'] = now
    session['_session_last_active'] = now
    session.permanent = was_permanent
    csrf_token()
    flash('Password changed successfully!', 'success')
    return redirect(url_for('dashboard'))


# --- Booking Receipt ---
@app.route('/booking/<int:booking_id>/receipt')
@login_required
def booking_receipt(booking_id):
    db = get_db()
    booking = db.execute('''
        SELECT b.*, p.title, p.compound, p.property_type, p.image_main,
               p.arrival_instructions, p.arrival_directions, p.nearby_essentials,
               p.emergency_contact_name, p.emergency_contact_phone,
               p.checkin_time, p.checkout_time, p.self_checkin_method,
               p.latitude AS property_latitude, p.longitude AS property_longitude,
               u.full_name as owner_name, u.email as owner_email, u.phone as owner_phone
        FROM bookings b
        JOIN properties p ON b.property_id = p.id
        JOIN users u ON p.owner_id = u.id
        WHERE b.id = ?
    ''', (booking_id,)).fetchone()

    if not booking:
        flash('Booking not found.', 'error')
        return redirect(url_for('dashboard'))

    # Only the tenant, the host, or an admin can view the receipt
    prop = db.execute('SELECT owner_id FROM properties WHERE id = ?', (booking['property_id'],)).fetchone()
    if not g.user['is_admin'] and booking['user_id'] != g.user['id'] and (not prop or prop['owner_id'] != g.user['id']):
        flash('Unauthorized.', 'error')
        return redirect(url_for('dashboard'))

    can_show_arrival = (
        prop and prop['owner_id'] == g.user['id']
    ) or (
        booking['user_id'] == g.user['id'] and booking['booking_status'] == 'confirmed'
    )
    payment_attempts = db.execute(
        '''SELECT tx_ref, status, provider_reference, created_at
           FROM payment_attempts WHERE booking_id = ?
           ORDER BY created_at DESC''',
        (booking_id,),
    ).fetchall()
    return render_template('receipt.html', booking=booking, can_show_arrival=can_show_arrival,
                           payment_attempts=payment_attempts)


# --- Payout Methods ---
@app.route('/payout/add', methods=['POST'])
@landlord_required
def add_payout_method():
    provider = request.form.get('provider', '').strip()
    account_name = request.form.get('account_name', '').strip()
    account_number = request.form.get('account_number', '').strip()
    bank_name = request.form.get('bank_name', '').strip()
    branch_code = request.form.get('branch_code', '').strip()

    allowed_providers = {'Bank Transfer', 'Mobile Money', 'Airtel Money', 'MTN Money', 'Zamtel Kwacha'}
    if not provider or not account_name or not account_number:
        flash('Provider, account name and account number are required.', 'error')
        return redirect(url_for('dashboard'))
    if provider not in allowed_providers:
        flash('Choose a valid payout provider.', 'error')
        return redirect(url_for('dashboard'))
    if (
        len(account_name) > 120
        or len(account_number) > 60
        or len(bank_name) > 120
        or len(branch_code) > 40
    ):
        flash('Payout details are too long.', 'error')
        return redirect(url_for('dashboard'))

    db = get_db()
    # Check count
    existing = db.execute('SELECT COUNT(*) FROM payout_methods WHERE user_id = ?', (g.user['id'],)).fetchone()[0]
    is_primary = 1 if existing == 0 else 0

    db.execute('''
        INSERT INTO payout_methods (user_id, provider, bank_name, account_name, account_number, branch_code, is_primary)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (g.user['id'], provider, bank_name, account_name, account_number, branch_code, is_primary))
    db.commit()
    flash('Payout method added!', 'success')
    return redirect(url_for('dashboard'))


@app.route('/payout/delete/<int:payout_id>', methods=['POST'])
@landlord_required
def delete_payout_method(payout_id):
    db = get_db()
    db.execute('DELETE FROM payout_methods WHERE id = ? AND user_id = ?', (payout_id, g.user['id']))
    db.commit()
    flash('Payout method removed.', 'info')
    return redirect(url_for('dashboard'))


# --- Enhanced Admin ---
@app.route('/admin/ban_user/<int:user_id>', methods=['POST'])
@admin_required
def admin_ban_user(user_id):
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if not user:
        flash('User not found.', 'error')
        return redirect(url_for('admin_users'))
    if user['is_admin']:
        flash('Cannot ban an admin.', 'error')
        return redirect(url_for('admin_users'))
    # Deactivate all their properties and invalidate all active sessions
    db.execute('UPDATE properties SET is_active = 0 WHERE owner_id = ?', (user_id,))
    db.execute(
        'UPDATE users SET role = ?, session_version = COALESCE(session_version, 1) + 1 WHERE id = ?',
        ('banned', user_id),
    )
    log_admin_action(db, 'user_banned', 'user', user_id, user['email'])
    db.commit()
    flash(f'User "{user["full_name"]}" has been banned.', 'info')
    return redirect(url_for('admin_users'))


@app.route('/admin/unban_user/<int:user_id>', methods=['POST'])
@admin_required
def admin_unban_user(user_id):
    db = get_db()
    result = db.execute("UPDATE users SET role = 'tenant' WHERE id = ? AND role = 'banned'", (user_id,))
    if result.rowcount:
        log_admin_action(db, 'user_unbanned', 'user', user_id)
    db.commit()
    flash('User unbanned.', 'success')
    return redirect(url_for('admin_users'))


@app.route('/admin/force_delist/<int:property_id>', methods=['POST'])
@admin_required
def admin_force_delist(property_id):
    db = get_db()
    db.execute('UPDATE properties SET is_active = 0 WHERE id = ?', (property_id,))
    log_admin_action(db, 'property_force_delisted', 'property', property_id)
    db.commit()
    flash('Property force-delisted by admin.', 'info')
    return redirect(url_for('admin_listings'))


@app.route('/admin/force_relist/<int:property_id>', methods=['POST'])
@admin_required
def admin_force_relist(property_id):
    db = get_db()
    cursor = db.execute(
        'UPDATE properties SET is_active = 1 WHERE id = ? AND is_active = 0',
        (property_id,),
    )
    if cursor.rowcount:
        property_row = db.execute(
            'SELECT * FROM properties WHERE id = ?', (property_id,)
        ).fetchone()
        notify_matching_searches(db, property_row, event='available')
        log_admin_action(db, 'property_force_relisted', 'property', property_id)
    db.commit()
    flash('Property re-listed by admin.', 'success')
    return redirect(url_for('admin_listings'))


if __name__ == '__main__':
    if not DATABASE_URL:
        ensure_db_schema()  # Check and apply schema changes
        if not os.path.exists(DATABASE):
            init_db()
            print("Initialized database.")

    app.run(debug=APP_ENV != 'production')
