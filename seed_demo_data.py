import argparse
import os
import secrets
import sqlite3
from pathlib import Path

from werkzeug.security import generate_password_hash

import app


PROJECT_DIR = Path(__file__).resolve().parent
IMAGE_IDS = [
    'photo-1600585154340-be6161a56a0c',
    'photo-1600607687939-ce8a6c25118c',
    'photo-1600566753086-00f18fb6b3ea',
    'photo-1600607687920-4e2a09cf159d',
    'photo-1600566753190-17f0baa2a6c3',
    'photo-1600607687644-c7171b42498f',
    'photo-1600566752355-35792bedcfea',
    'photo-1600607687939-ce8a6c25118c',
    'photo-1564013799919-ab600027ffc6',
    'photo-1571896349842-33c89424de2d',
    'photo-1566073771259-6a8506099945',
    'photo-1566665797739-1674de7a421a',
    'photo-1542314831-068cd1dbfeeb',
    'photo-1600566753376-12c8ab7fb75b',
    'photo-1600607687939-ce8a6c25118c',
    'photo-1600607687920-4e2a09cf159d',
    'photo-1600566753086-00f18fb6b3ea',
    'photo-1600566753190-17f0baa2a6c3',
    'photo-1600607687644-c7171b42498f',
    'photo-1600585154340-be6161a56a0c',
    'photo-1600585154340-be6161a56a0c',
    'photo-1600607687939-ce8a6c25118c',
    'photo-1600566753086-00f18fb6b3ea',
    'photo-1600607687920-4e2a09cf159d',
]

LISTINGS = [
    {
        'title': '[SAMPLE] Jacaranda Family House',
        'compound': 'Kabulonga',
        'property_type': 'House',
        'price': 9800,
        'period': 'month',
        'bedrooms': 3,
        'bathrooms': 2,
        'capacity': 6,
        'description': 'Fictional furnished family home for testing monthly rental searches, booking totals, and amenities.',
        'power': 'solar_backup',
        'water': 'municipal_and_borehole',
        'internet': 'reliable_wifi',
        'speed': 25,
        'solar': 1,
        'borehole': 1,
        'pool': 0,
        'garden': 1,
        'ac': 0,
        'wifi': 1,
        'parking': 1,
        'cleaning': 350,
        'deposit': 1200,
    },
    {
        'title': '[SAMPLE] Greenview Starter Home',
        'compound': 'Bauleni',
        'property_type': 'House',
        'price': 4200,
        'period': 'month',
        'bedrooms': 2,
        'bathrooms': 1,
        'capacity': 4,
        'description': 'Fictional two-bedroom home with simple furnishings, created for testing affordable monthly listings.',
        'power': 'grid_only',
        'water': 'storage_tank',
        'internet': 'mobile_data',
        'speed': None,
        'solar': 0,
        'borehole': 0,
        'pool': 0,
        'garden': 0,
        'ac': 0,
        'wifi': 0,
        'parking': 1,
        'cleaning': 0,
        'deposit': 500,
    },
    {
        'title': '[SAMPLE] Chalala Garden Cottage',
        'compound': 'Chalala',
        'property_type': 'House',
        'price': 6500,
        'period': 'month',
        'bedrooms': 2,
        'bathrooms': 2,
        'capacity': 4,
        'description': 'Fictional garden cottage with a private kitchen and outdoor space for listing detail-page testing.',
        'power': 'generator_backup',
        'water': 'borehole',
        'internet': 'variable_wifi',
        'speed': 10,
        'solar': 0,
        'borehole': 1,
        'pool': 0,
        'garden': 1,
        'ac': 0,
        'wifi': 1,
        'parking': 1,
        'cleaning': 200,
        'deposit': 800,
    },
    {
        'title': '[SAMPLE] Chilenje Family Bungalow',
        'compound': 'Chilenje',
        'property_type': 'House',
        'price': 5700,
        'period': 'month',
        'bedrooms': 3,
        'bathrooms': 2,
        'capacity': 5,
        'description': 'Fictional single-storey bungalow with a sitting room, suitable for testing bedroom and price filters.',
        'power': 'solar_and_generator',
        'water': 'municipal',
        'internet': 'reliable_wifi',
        'speed': 20,
        'solar': 1,
        'borehole': 0,
        'pool': 0,
        'garden': 1,
        'ac': 0,
        'wifi': 1,
        'parking': 1,
        'cleaning': 250,
        'deposit': 700,
    },
    {
        'title': '[SAMPLE] Ibex Hill Modern Residence',
        'compound': 'Ibex Hill',
        'property_type': 'House',
        'price': 12500,
        'period': 'month',
        'bedrooms': 4,
        'bathrooms': 3,
        'capacity': 8,
        'description': 'Fictional spacious home with a pool and air conditioning for testing premium listing filters.',
        'power': 'solar_backup',
        'water': 'municipal_and_borehole',
        'internet': 'reliable_wifi',
        'speed': 50,
        'solar': 1,
        'borehole': 1,
        'pool': 1,
        'garden': 1,
        'ac': 1,
        'wifi': 1,
        'parking': 1,
        'cleaning': 500,
        'deposit': 2000,
    },
    {
        'title': '[SAMPLE] Kabwata Courtyard Home',
        'compound': 'Kabwata',
        'property_type': 'House',
        'price': 5000,
        'period': 'month',
        'bedrooms': 2,
        'bathrooms': 1,
        'capacity': 4,
        'description': 'Fictional compact home with a shared courtyard, included to test mid-range rental comparisons.',
        'power': 'grid_only',
        'water': 'municipal',
        'internet': 'mobile_data',
        'speed': None,
        'solar': 0,
        'borehole': 0,
        'pool': 0,
        'garden': 1,
        'ac': 0,
        'wifi': 0,
        'parking': 0,
        'cleaning': 150,
        'deposit': 600,
    },
    {
        'title': '[SAMPLE] Kalundu Executive House',
        'compound': 'Kalundu',
        'property_type': 'House',
        'price': 10500,
        'period': 'month',
        'bedrooms': 4,
        'bathrooms': 3,
        'capacity': 8,
        'description': 'Fictional executive-style home with a private garden and backup power for amenity testing.',
        'power': 'generator_backup',
        'water': 'borehole',
        'internet': 'reliable_wifi',
        'speed': 30,
        'solar': 0,
        'borehole': 1,
        'pool': 0,
        'garden': 1,
        'ac': 1,
        'wifi': 1,
        'parking': 1,
        'cleaning': 400,
        'deposit': 1500,
    },
    {
        'title': '[SAMPLE] Longacres City Townhouse',
        'compound': 'Longacres',
        'property_type': 'House',
        'price': 8800,
        'period': 'month',
        'bedrooms': 3,
        'bathrooms': 2,
        'capacity': 6,
        'description': 'Fictional furnished townhouse for testing central-neighbourhood searches and monthly pricing.',
        'power': 'solar_backup',
        'water': 'storage_tank',
        'internet': 'variable_wifi',
        'speed': 15,
        'solar': 1,
        'borehole': 0,
        'pool': 0,
        'garden': 0,
        'ac': 1,
        'wifi': 1,
        'parking': 1,
        'cleaning': 300,
        'deposit': 1000,
    },
    {
        'title': '[SAMPLE] Makeni Family Bungalow',
        'compound': 'Makeni',
        'property_type': 'House',
        'price': 6100,
        'period': 'month',
        'bedrooms': 3,
        'bathrooms': 2,
        'capacity': 6,
        'description': 'Fictional family bungalow with a borehole and garden, created for water-supply filter testing.',
        'power': 'grid_only',
        'water': 'borehole',
        'internet': 'mobile_data',
        'speed': None,
        'solar': 0,
        'borehole': 1,
        'pool': 0,
        'garden': 1,
        'ac': 0,
        'wifi': 0,
        'parking': 1,
        'cleaning': 200,
        'deposit': 700,
    },
    {
        'title': '[SAMPLE] Meanwood Starter House',
        'compound': 'Meanwood',
        'property_type': 'House',
        'price': 4700,
        'period': 'month',
        'bedrooms': 2,
        'bathrooms': 1,
        'capacity': 4,
        'description': 'Fictional two-bedroom starter home with parking for testing lower-price search results.',
        'power': 'solar_backup',
        'water': 'storage_tank',
        'internet': 'variable_wifi',
        'speed': 8,
        'solar': 1,
        'borehole': 0,
        'pool': 0,
        'garden': 0,
        'ac': 0,
        'wifi': 1,
        'parking': 1,
        'cleaning': 0,
        'deposit': 500,
    },
    {
        'title': '[SAMPLE] New Kasama Business Hotel',
        'compound': 'New Kasama',
        'property_type': 'Hotel',
        'price': 1650,
        'period': 'night',
        'bedrooms': 1,
        'bathrooms': 1,
        'capacity': 2,
        'description': 'Fictional hotel room with breakfast-area and Wi-Fi amenities for testing nightly bookings.',
        'power': 'solar_and_generator',
        'water': 'municipal_and_borehole',
        'internet': 'reliable_wifi',
        'speed': 40,
        'solar': 1,
        'borehole': 1,
        'pool': 1,
        'garden': 0,
        'ac': 1,
        'wifi': 1,
        'parking': 1,
        'cleaning': 0,
        'deposit': 0,
    },
    {
        'title': '[SAMPLE] Rhodes Park City Hotel',
        'compound': 'Rhodes Park',
        'property_type': 'Hotel',
        'price': 1350,
        'period': 'night',
        'bedrooms': 1,
        'bathrooms': 1,
        'capacity': 2,
        'description': 'Fictional central hotel room for testing nightly prices, location filters, and booking checkout.',
        'power': 'generator_backup',
        'water': 'storage_tank',
        'internet': 'reliable_wifi',
        'speed': 25,
        'solar': 0,
        'borehole': 0,
        'pool': 0,
        'garden': 0,
        'ac': 1,
        'wifi': 1,
        'parking': 1,
        'cleaning': 0,
        'deposit': 300,
    },
    {
        'title': '[SAMPLE] Roma Garden Hotel',
        'compound': 'Roma',
        'property_type': 'Hotel',
        'price': 2100,
        'period': 'night',
        'bedrooms': 1,
        'bathrooms': 1,
        'capacity': 2,
        'description': 'Fictional hotel room with garden and pool amenities for testing premium nightly listings.',
        'power': 'solar_backup',
        'water': 'borehole',
        'internet': 'reliable_wifi',
        'speed': 50,
        'solar': 1,
        'borehole': 1,
        'pool': 1,
        'garden': 1,
        'ac': 1,
        'wifi': 1,
        'parking': 1,
        'cleaning': 0,
        'deposit': 500,
    },
    {
        'title': '[SAMPLE] Woodlands Comfort Hotel',
        'compound': 'Woodlands',
        'property_type': 'Hotel',
        'price': 1100,
        'period': 'night',
        'bedrooms': 1,
        'bathrooms': 1,
        'capacity': 2,
        'description': 'Fictional comfortable hotel room with air conditioning for testing value nightly stays.',
        'power': 'grid_only',
        'water': 'municipal',
        'internet': 'variable_wifi',
        'speed': 12,
        'solar': 0,
        'borehole': 0,
        'pool': 0,
        'garden': 0,
        'ac': 1,
        'wifi': 1,
        'parking': 1,
        'cleaning': 0,
        'deposit': 200,
    },
    {
        'title': '[SAMPLE] Chilenje Guest Hotel',
        'compound': 'Chilenje South',
        'property_type': 'Hotel',
        'price': 850,
        'period': 'night',
        'bedrooms': 1,
        'bathrooms': 1,
        'capacity': 2,
        'description': 'Fictional budget hotel room for testing low nightly prices and essential amenities.',
        'power': 'grid_only',
        'water': 'storage_tank',
        'internet': 'mobile_data',
        'speed': None,
        'solar': 0,
        'borehole': 0,
        'pool': 0,
        'garden': 0,
        'ac': 0,
        'wifi': 0,
        'parking': 1,
        'cleaning': 0,
        'deposit': 0,
    },
    {
        'title': '[SAMPLE] Leopards Hill Glasshouse Villa',
        'compound': 'Leopards Hill',
        'property_type': 'Villa',
        'price': 3200,
        'period': 'night',
        'bedrooms': 4,
        'bathrooms': 4,
        'capacity': 8,
        'description': 'Fictional premium villa with a private pool, landscaped garden, generous living areas, and panoramic Lusaka views. Sample listing for testing upscale searches and nightly checkout.',
        'power': 'solar_and_generator',
        'water': 'municipal_and_borehole',
        'internet': 'reliable_wifi',
        'speed': 100,
        'solar': 1,
        'borehole': 1,
        'pool': 1,
        'garden': 1,
        'ac': 1,
        'wifi': 1,
        'parking': 1,
        'cleaning': 450,
        'deposit': 2500,
    },
    {
        'title': '[SAMPLE] State Lodge Courtyard Villa',
        'compound': 'State Lodge',
        'property_type': 'Villa',
        'price': 2450,
        'period': 'night',
        'bedrooms': 3,
        'bathrooms': 3,
        'capacity': 6,
        'description': 'Fictional contemporary villa with a private courtyard, outdoor dining, backup power, and dedicated parking. Designed for testing premium family stays.',
        'power': 'solar_backup',
        'water': 'borehole',
        'internet': 'reliable_wifi',
        'speed': 50,
        'solar': 1,
        'borehole': 1,
        'pool': 0,
        'garden': 1,
        'ac': 1,
        'wifi': 1,
        'parking': 1,
        'cleaning': 350,
        'deposit': 1800,
    },
    {
        'title': '[SAMPLE] Chamba Valley Executive Guest House',
        'compound': 'Chamba Valley',
        'property_type': 'Guest House',
        'price': 1550,
        'period': 'night',
        'bedrooms': 2,
        'bathrooms': 2,
        'capacity': 4,
        'description': 'Fictional boutique guest house with a quiet garden, private kitchen, breakfast nook, and secure parking for guests testing short stays.',
        'power': 'generator_backup',
        'water': 'municipal_and_borehole',
        'internet': 'reliable_wifi',
        'speed': 35,
        'solar': 0,
        'borehole': 1,
        'pool': 0,
        'garden': 1,
        'ac': 1,
        'wifi': 1,
        'parking': 1,
        'cleaning': 150,
        'deposit': 700,
    },
    {
        'title': '[SAMPLE] Kabulonga Palm Boutique Guest House',
        'compound': 'Kabulonga',
        'property_type': 'Guest House',
        'price': 1850,
        'period': 'night',
        'bedrooms': 2,
        'bathrooms': 2,
        'capacity': 4,
        'description': 'Fictional boutique guest house in a leafy setting with a pool, lounge, reliable Wi-Fi, and staff-assisted check-in for premium listing tests.',
        'power': 'solar_and_generator',
        'water': 'municipal_and_borehole',
        'internet': 'reliable_wifi',
        'speed': 75,
        'solar': 1,
        'borehole': 1,
        'pool': 1,
        'garden': 1,
        'ac': 1,
        'wifi': 1,
        'parking': 1,
        'cleaning': 200,
        'deposit': 1000,
    },
]


def image_url(photo_id):
    return f'https://images.unsplash.com/{photo_id}?auto=format&fit=crop&w=1400&q=85'


def seed(database_path, reset_demo_password=False):
    database_path = database_path.resolve()
    app.DATABASE = str(database_path)
    app.ensure_db_schema()

    conn = sqlite3.connect(database_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')

    created_accounts = []
    created_listings = 0
    created_by_type = {'House': 0, 'Hotel': 0, 'Villa': 0, 'Guest House': 0}
    created_photos = 0
    password = f'Demo-{secrets.token_urlsafe(12)}7'
    admin_password = f'Admin-{secrets.token_urlsafe(12)}7'

    try:
        conn.execute('BEGIN IMMEDIATE')

        owners = []
        owner_count = (len(LISTINGS) + 2) // 3
        for index in range(owner_count):
            account_number = index + 1
            email = f'demo.landlord{account_number:02d}@kwachastay.test'
            user = conn.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()
            if user:
                owner_id = user['id']
                account = conn.execute(
                    'SELECT full_name, role FROM users WHERE id = ?', (owner_id,)
                ).fetchone()
                if account['full_name'] != f'Demo Landlord {account_number:02d}' or account['role'] != 'owner':
                    raise ValueError(f'Cannot seed demo account because {email} is already in use.')
                if reset_demo_password:
                    conn.execute(
                        'UPDATE users SET password = ? WHERE id = ?',
                        (generate_password_hash(password), owner_id),
                    )
            else:
                cursor = conn.execute(
                    '''INSERT INTO users (full_name, email, phone, password, role)
                       VALUES (?, ?, ?, ?, 'owner')''',
                    (
                        f'Demo Landlord {account_number:02d}',
                        email,
                        f'+260 000 000 {account_number:03d}',
                        generate_password_hash(password),
                    ),
                )
                owner_id = cursor.lastrowid
                created_accounts.append(email)
            owners.append(owner_id)

        admin_email = 'demo.admin@kwachastay.test'
        if reset_demo_password:
            admin = conn.execute(
                'SELECT id, full_name FROM users WHERE email = ?', (admin_email,)
            ).fetchone()
            if admin:
                if admin['full_name'] != 'KwachaStay Demo Admin':
                    raise ValueError(f'Cannot seed demo admin because {admin_email} is already in use.')
                conn.execute(
                    'UPDATE users SET is_admin = 1, password = ? WHERE id = ?',
                    (generate_password_hash(admin_password), admin['id']),
                )
            else:
                conn.execute(
                    '''INSERT INTO users (full_name, email, phone, password, role, is_admin)
                       VALUES (?, ?, ?, ?, 'tenant', 1)''',
                    (
                        'KwachaStay Demo Admin',
                        admin_email,
                        '+260 000 000 000',
                        generate_password_hash(admin_password),
                    ),
                )

        property_columns = (
            'owner_id', 'title', 'description', 'price_per_night', 'price_period',
            'compound', 'property_type', 'bed_type', 'room_capacity', 'kitchen_type',
            'has_sitting_room', 'has_solar', 'has_borehole', 'has_pool', 'has_garden',
            'has_bbq', 'has_balcony', 'has_ac', 'has_wifi', 'has_parking',
            'is_verified', 'is_active', 'latitude', 'longitude', 'image_main',
            'cancellation_policy', 'house_rules', 'cleaning_fee', 'refundable_deposit',
            'utilities_included', 'power_backup', 'water_supply', 'internet_availability',
            'internet_speed_mbps', 'arrival_instructions', 'arrival_directions',
            'nearby_essentials', 'main_photo_category', 'bedrooms', 'bathrooms',
            'listing_category', 'availability_status', 'location_details',
        )
        placeholders = ', '.join('?' for _ in property_columns)
        insert_property = (
            f'INSERT INTO properties ({", ".join(property_columns)}) '
            f'VALUES ({placeholders})'
        )

        for index, listing in enumerate(LISTINGS):
            owner_id = owners[index // 3]
            existing = conn.execute(
                'SELECT id, owner_id FROM properties WHERE title = ?',
                (listing['title'],),
            ).fetchone()
            if existing:
                if existing['owner_id'] != owner_id:
                    raise ValueError(
                        f'Cannot seed "{listing["title"]}": that title belongs to another account.'
                    )
                continue

            main_image = image_url(IMAGE_IDS[index])
            details = (
                owner_id,
                listing['title'],
                'SAMPLE DATA ONLY. ' + listing['description']
                + ' This fictional listing is for local testing and is not a real accommodation.',
                listing['price'],
                listing['period'],
                listing['compound'],
                listing['property_type'],
                'King' if listing['property_type'] == 'Hotel' else None,
                listing['capacity'],
                'None' if listing['property_type'] == 'Hotel' else 'Private',
                int(listing['property_type'] == 'House'),
                listing['solar'],
                listing['borehole'],
                listing['pool'],
                listing['garden'],
                0,
                int(listing['property_type'] == 'House'),
                listing['ac'],
                listing['wifi'],
                listing['parking'],
                0,
                1,
                None,
                None,
                main_image,
                'moderate',
                'SAMPLE RULES ONLY. Confirm real property rules with a verified host.',
                listing['cleaning'],
                listing['deposit'],
                1,
                listing['power'],
                listing['water'],
                listing['internet'],
                listing['speed'],
                'SAMPLE ONLY. No real check-in details are provided for this listing.',
                'Fictional neighbourhood-level sample. No exact address or map pin is supplied.',
                'SAMPLE ONLY. Verify local shops and services before relying on this information.',
                'bedroom' if listing['property_type'] == 'Hotel' else 'living_area',
                listing['bedrooms'],
                listing['bathrooms'],
                'rental',
                'available',
                f'Fictional sample location in {listing["compound"]}; no exact address is provided.',
            )
            cursor = conn.execute(insert_property, details)
            property_id = cursor.lastrowid
            created_listings += 1
            created_by_type[listing['property_type']] += 1

            for photo_offset, category in enumerate(('bedroom', 'bathroom', 'entrance'), start=1):
                photo_id = IMAGE_IDS[(index + photo_offset) % len(IMAGE_IDS)]
                conn.execute(
                    '''INSERT INTO property_images (property_id, image_url, category)
                       VALUES (?, ?, ?)''',
                    (property_id, image_url(photo_id), category),
                )
                created_photos += 1

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    type_summary = ', '.join(
        f'{count} {kind.lower()}' + ('' if count == 1 else 's')
        for kind, count in created_by_type.items() if count
    )
    print(f'Demo listings added: {created_listings} ({type_summary})')
    print(f'Demo landlord accounts added: {len(created_accounts)}')
    print(f'Demo listing photos added: {created_photos}')

    if created_accounts:
        print('\nNew demo landlord login details:')
        print(f'Password for the new accounts: {password}')
        for email in created_accounts:
            print(f'  {email}')
    else:
        print('Demo accounts already exist; their passwords were left unchanged.')
    if reset_demo_password:
        print('\nDemo landlord login (password reset for all demo landlords):')
        print('  Email: demo.landlord01@kwachastay.test')
        print(f'  Password: {password}')
        print('\nDemo admin login (local testing only):')
        print(f'  Email: {admin_email}')
        print(f'  Password: {admin_password}')
        print('Do not use these demo accounts on a public or production site.')


def main():
    parser = argparse.ArgumentParser(
        description='Add clearly labeled fictional KwachaStay listings and landlord accounts.'
    )
    parser.add_argument(
        '--database',
        type=Path,
        default=PROJECT_DIR / 'kwachastay.db',
        help='SQLite database file (default: kwachastay.db in the project folder)',
    )
    parser.add_argument(
        '--reset-demo-password',
        action='store_true',
        help='Reset all demo landlord passwords and create/reset the demo admin login; prints new credentials.',
    )
    args = parser.parse_args()

    os.chdir(PROJECT_DIR)
    seed(args.database, reset_demo_password=args.reset_demo_password)


if __name__ == '__main__':
    main()
