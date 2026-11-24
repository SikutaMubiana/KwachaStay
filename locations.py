"""Scalable geographic location registry for KwachaStay.

Current Launch Scope (Seven-City Launch):
    Lusaka, Kitwe, Livingstone, Kabwe, Solwezi, Chipata, Ndola.

How to scale to additional Zambian cities or provinces in future releases:
    Add a single city definition to `LAUNCH_CITIES` below with its `province`,
    `coords`, `neighbourhoods`, `landmarks`, and guide metadata. All dropdowns,
    search filters, validation rules, city guides, geocoder matches, and map
    centres derive automatically from `LAUNCH_CITIES`.
"""

ZAMBIA_DEFAULT_CENTER = (-14.2000, 28.3000)
ZAMBIA_DEFAULT_ZOOM = 6

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

# Controlled Seven-City Launch Registry
# Only these seven Zambian cities are enabled at launch.
LAUNCH_CITIES = {
    'Lusaka': {
        'slug': 'lusaka',
        'province': 'Lusaka Province',
        'coords': (-15.4167, 28.2833),
        'neighbourhoods': sorted(LUSAKA_NEIGHBOURHOOD_COORDS.keys()),
        'neighbourhood_coords': LUSAKA_NEIGHBOURHOOD_COORDS,
        'landmarks': [
            ('KKIA Airport', 'fa-plane', -15.3302, 28.4526),
            ('EastPark Mall', 'fa-bag-shopping', -15.3988, 28.3304),
            ('Manda Hill Mall', 'fa-bag-shopping', -15.3917, 28.3090),
            ('University of Zambia (UNZA)', 'fa-graduation-cap', -15.3917, 28.3292),
            ('Levy Junction', 'fa-building', -15.3915, 28.2806),
            ('Centro Mall (Kabulonga)', 'fa-bag-shopping', -15.4242, 28.3528),
            ('Lusaka CBD', 'fa-city', -15.4167, 28.2833),
        ],
        'featured_neighbourhoods': ['Kabulonga', 'Rhodes Park', 'Ibex Hill', 'Woodlands', 'Chalala', 'Roma', 'Avondale'],
        'overview': 'Zambia’s capital and commercial hub, offering family homes, apartments, student boarding houses near major campuses, and short-term hotels and villas.',
        'good_for': 'Families, professionals, university students, business travellers, and short-stay guests.',
        'tip': 'Confirm proximity to your daily commute, backup power, and water setup when choosing between eastern, central, and southern suburbs.',
    },
    'Kitwe': {
        'slug': 'kitwe',
        'province': 'Copperbelt Province',
        'coords': (-12.8024, 28.2132),
        'neighbourhoods': sorted([
            'Buchi', 'Bulangililo', 'Buyantanshi', 'Chamboli', 'Chibote',
            'Chimwemwe', 'Garneton', 'Ipusukilo', 'Itimpi', 'Kamfinsa',
            'Kamitondo', 'Kawama', 'Kitwe CBD', 'Kwacha', 'Kwacha East',
            'Luangwa', 'Mindolo', 'Mindolo North', 'Miseshi', 'Mulenga',
            'Ndeke', 'Ndeke Village', 'Nkana East', 'Nkana West', 'Parklands',
            'Racecourse', 'Riverside', 'Riverside Extension', 'Twatasha',
            'Wusakile', 'Zamtan',
        ]),
        'neighbourhood_coords': {},
        'landmarks': [
            ('Copperbelt University (CBU)', 'fa-graduation-cap', -12.8054, 28.2414),
            ('Mukuba Mall', 'fa-bag-shopping', -12.8091, 28.2345),
            ('Kitwe Teaching Hospital', 'fa-hospital', -12.8127, 28.2145),
            ('Kitwe CBD', 'fa-city', -12.8024, 28.2132),
        ],
        'featured_neighbourhoods': ['Riverside', 'Parklands', 'Nkana East', 'Nkana West', 'Garneton', 'Kwacha East'],
        'overview': 'A major Copperbelt commercial and university city, home to Copperbelt University (CBU) and vibrant residential neighbourhoods.',
        'good_for': 'CBU students, mining & engineering professionals, families, and Copperbelt visitors.',
        'tip': 'Riverside and Parklands are popular near CBU and Mukuba Mall, while Nkana East, Nkana West, and Garneton offer established residential living.',
    },
    'Livingstone': {
        'slug': 'livingstone',
        'province': 'Southern Province',
        'coords': (-17.8419, 25.8542),
        'neighbourhoods': sorted([
            'Airport Area', 'Dambwa Central', 'Dambwa North', 'Dambwa Site',
            'Ellaine Brittel', 'Falls Park', 'Highlands', 'Libuyu', 'Linda',
            'Malota', 'Maramba', 'Mosi-oa-Tunya / Riverfront', 'Nottie Broad',
            'Sakubita', 'Simonga', 'Town Centre', 'Victoria Falls Road',
            'Zambezi Sawmills',
        ]),
        'neighbourhood_coords': {},
        'landmarks': [
            ('Harry Mwanga Nkumbula Airport (LVI)', 'fa-plane', -17.8218, 25.8227),
            ('Victoria Falls (Mosi-oa-Tunya)', 'fa-water', -17.9243, 25.8572),
            ('Livingstone Town Centre', 'fa-city', -17.8419, 25.8542),
        ],
        'featured_neighbourhoods': ['Highlands', 'Town Centre', 'Mosi-oa-Tunya / Riverfront', 'Nottie Broad', 'Dambwa North', 'Falls Park'],
        'overview': 'Zambia’s tourism capital near Victoria Falls, combining hospitality lodges, villas, guest houses, and quiet residential neighbourhoods.',
        'good_for': 'Leisure travellers, couples, families, hospitality staff, and long-term residents.',
        'tip': 'Check distance to Victoria Falls Road, the airport, or Town Centre depending on whether you are visiting for tourism or longer-term work.',
    },
    'Kabwe': {
        'slug': 'kabwe',
        'province': 'Central Province',
        'coords': (-14.4469, 28.4464),
        'neighbourhoods': sorted([
            'Bwacha', 'Chindwin', 'Chowa', 'Highridge', 'Kabwe CBD',
            'Kasanda', 'Katondo', 'Luangwa', 'Lukanga', 'Makululu',
            'Mine Area', 'Mpima', 'Mulungushi', 'Nakoli', 'Natuseko',
            'Ngungu', 'Pollen', 'Railways', 'Waya',
        ]),
        'neighbourhood_coords': {},
        'landmarks': [
            ('Mulungushi University (Town Campus)', 'fa-graduation-cap', -14.4420, 28.4470),
            ('Kabwe Mall', 'fa-bag-shopping', -14.4368, 28.4448),
            ('Kabwe CBD', 'fa-city', -14.4469, 28.4464),
        ],
        'featured_neighbourhoods': ['Highridge', 'Kabwe CBD', 'Mulungushi', 'Luangwa', 'Bwacha', 'Chowa'],
        'overview': 'Central Province’s provincial capital along the Great North Road, serving students, civil servants, families, and transit travellers.',
        'good_for': 'Mulungushi University students, long-term workers, families, and travellers between Lusaka and the Copperbelt.',
        'tip': 'Highridge and Kabwe CBD are well located for town services, while Mulungushi and surrounding areas suit students and commuters.',
    },
    'Solwezi': {
        'slug': 'solwezi',
        'province': 'North-Western Province',
        'coords': (-12.1688, 26.3894),
        'neighbourhoods': sorted([
            'College Area', 'Kandemba', 'Kazomba', 'Kimasala', 'Kimiteto',
            'Kyalalankuba', 'Kyawama', 'Messengers', 'Mitec', 'Mitukutuku',
            'Mushitala', 'Muzabula', 'Royal', 'Solwezi CBD', 'Urban',
            'Weighbridge', 'Wisdom',
        ]),
        'neighbourhood_coords': {},
        'landmarks': [
            ('Solwezi Airport', 'fa-plane', -12.1719, 26.3669),
            ('City Mall Solwezi', 'fa-bag-shopping', -12.1786, 26.3947),
            ('Solwezi CBD', 'fa-city', -12.1688, 26.3894),
        ],
        'featured_neighbourhoods': ['Kimasala', 'Mushitala', 'Solwezi CBD', 'Kyawama', 'College Area', 'Urban'],
        'overview': 'North-Western Province’s fast-growing mining and business hub with residential estates, corporate apartments, lodges, and family homes.',
        'good_for': 'Mining and corporate professionals, contractors, relocating families, and business travellers.',
        'tip': 'Confirm water backup, paved access, and travel time to Solwezi CBD or work sites when comparing properties.',
    },
    'Chipata': {
        'slug': 'chipata',
        'province': 'Eastern Province',
        'coords': (-13.6333, 32.6500),
        'neighbourhoods': sorted([
            'Chipata CBD', 'Gondar', 'Hillside', 'Kanjala', 'Kapata',
            'Little Bombay', 'Magazine', 'Mchini', 'Moth', 'Nabvutika',
            'Nsingo', 'Old Jim', 'St. Annes', 'Umodzi', 'Walela',
        ]),
        'neighbourhood_coords': {},
        'landmarks': [
            ('Chipata Airport', 'fa-plane', -13.5642, 32.5872),
            ('Great East Mall (Chipata)', 'fa-bag-shopping', -13.6406, 32.6462),
            ('Chipata CBD', 'fa-city', -13.6333, 32.6500),
        ],
        'featured_neighbourhoods': ['Kanjala', 'Hillside', 'Chipata CBD', 'Moth', 'Kapata', 'Little Bombay'],
        'overview': 'Eastern Province’s lively commercial gateway, offering residential houses, apartments, guest houses, and short-stay accommodation.',
        'good_for': 'Families, regional professionals, students, cross-border business travellers, and visitors to Eastern Province.',
        'tip': 'Kanjala, Hillside, and Moth are established residential spots with convenient access to Chipata CBD and Great East Road.',
    },
    'Ndola': {
        'slug': 'ndola',
        'province': 'Copperbelt Province',
        'coords': (-12.9587, 28.6366),
        'neighbourhoods': sorted([
            'Broadway', 'Chifubu', 'Chipulukusu', 'Dola Hill', 'Fatmols',
            'Hillcrest', 'Industrial Area', 'Itawa', 'Kabushi', 'Kaloko',
            'Kanini', 'Kansenshi', 'Kawama', 'Lubuto', 'Masala', 'Mushili',
            'Ndeke', 'Ndola CBD', 'New Masala', 'Northrise', 'Pamodzi',
            'Skyways', 'Twapia',
        ]),
        'neighbourhood_coords': {},
        'landmarks': [
            ('Simon Mwansa Kapwepwe Airport', 'fa-plane', -12.9981, 28.6649),
            ('Kafubu Mall', 'fa-bag-shopping', -12.9690, 28.6410),
            ('Ndola Teaching Hospital', 'fa-hospital', -12.9718, 28.6373),
            ('Ndola CBD', 'fa-city', -12.9587, 28.6366),
        ],
        'featured_neighbourhoods': ['Kansenshi', 'Northrise', 'Itawa', 'Hillcrest', 'Kanini', 'Ndola CBD'],
        'overview': 'The Copperbelt’s provincial capital and aviation gateway, featuring quiet residential suburbs, apartments, student rentals, and business hotels.',
        'good_for': 'Professionals, families, college students, business travellers, and Copperbelt visitors.',
        'tip': 'Kansenshi, Northrise, and Itawa are popular residential areas, while Broadway and Ndola CBD give quick access to offices and the airport.',
    },
}

# Derived structures used across the entire application
ZAMBIA_CITIES = list(LAUNCH_CITIES.keys())
ZAMBIA_CITY_COORDS = {city: data['coords'] for city, data in LAUNCH_CITIES.items()}
ZAMBIA_CITY_NEIGHBOURHOODS = {city: data['neighbourhoods'] for city, data in LAUNCH_CITIES.items()}
CITY_KEY_LANDMARKS = {city: data['landmarks'] for city, data in LAUNCH_CITIES.items()}
LUSAKA_NEIGHBOURHOODS = ZAMBIA_CITY_NEIGHBOURHOODS['Lusaka']
LUSAKA_DEFAULT_COORDS = ZAMBIA_CITY_COORDS['Lusaka']

# Institutions located across our seven launch cities
ZAMBIA_UNIVERSITIES = [
    'UNZA (Great East Road, Lusaka)',
    'UNZA (Ridgeway Campus, Lusaka)',
    'Copperbelt University — CBU (Kitwe)',
    'UNILUS (Silverest Campus, Lusaka)',
    'UNILUS (Pioneer Campus, Lusaka)',
    'Mulungushi University (Kabwe)',
    'Cavendish University (Lusaka)',
    'Lusaka Apex Medical University',
    'Evelyn Hone College (Lusaka)',
    'ZCAS University (Lusaka)',
    'NIPA (Lusaka)',
    'Texila American University (Lusaka)',
    'Eden University (Lusaka)',
    'Copperstone University (Kitwe)',
    'Levy Mwanawasa Medical University (LMMU, Lusaka)',
    'Zambia University College of Technology (Ndola)',
    'Livingstone International University (LIUTEBM, Livingstone)',
    'Solwezi Trades Training Institute (Solwezi)',
    'Chipata College of Education / Trades (Chipata)',
    'Other College / Institution',
]


def is_supported_city(city):
    return bool(city and city.strip() in LAUNCH_CITIES)


def normalize_launch_city(raw_city, *, allow_empty_default=None):
    """Validate and return a canonical launch city name.

    If `raw_city` is empty:
        - returns `allow_empty_default` when provided (e.g. 'Lusaka' for legacy API callers
          or '' for optional registration preferences).
        - otherwise raises ValueError.
    If `raw_city` is non-empty and not one of the seven launch cities, raises ValueError.
    """
    value = (raw_city or '').strip()
    if not value:
        if allow_empty_default is not None:
            return allow_empty_default
        raise ValueError(
            'Select one of our seven launch cities: ' + ', '.join(ZAMBIA_CITIES) + '.'
        )
    for city in ZAMBIA_CITIES:
        if city.casefold() == value.casefold():
            return city
    raise ValueError(
        'KwachaStay currently serves seven Zambian cities: ' + ', '.join(ZAMBIA_CITIES) + '.'
    )


def get_city_neighbourhoods(city):
    if city in ZAMBIA_CITY_NEIGHBOURHOODS:
        return ZAMBIA_CITY_NEIGHBOURHOODS[city]
    return []


def get_city_landmarks(city=None):
    """Return landmark list for a specific launch city, or all launch cities grouped."""
    if city and city in CITY_KEY_LANDMARKS:
        return CITY_KEY_LANDMARKS[city]
    return CITY_KEY_LANDMARKS


def get_neighbourhood_coordinates(compound, city=None):
    city_name = (city or '').strip()
    if compound:
        needle = compound.strip().casefold()
        if city_name in LAUNCH_CITIES:
            city_coords_map = LAUNCH_CITIES[city_name].get('neighbourhood_coords') or {}
            if compound in city_coords_map:
                return city_coords_map[compound]
            for name, coords in city_coords_map.items():
                if name.casefold() == needle:
                    return coords
            return LAUNCH_CITIES[city_name]['coords']
        # No city specified — check known neighbourhood maps across launch cities
        for c_data in LAUNCH_CITIES.values():
            cmap = c_data.get('neighbourhood_coords') or {}
            if compound in cmap:
                return cmap[compound]
            for name, coords in cmap.items():
                if name.casefold() == needle:
                    return coords
    if city_name in ZAMBIA_CITY_COORDS:
        return ZAMBIA_CITY_COORDS[city_name]
    return ZAMBIA_DEFAULT_CENTER


def build_city_guide():
    """Return structured guide cards for all launch cities."""
    guide = []
    for name, data in LAUNCH_CITIES.items():
        guide.append({
            'name': name,
            'slug': data['slug'],
            'province': data['province'],
            'coords': data['coords'],
            'overview': data['overview'],
            'good_for': data['good_for'],
            'tip': data['tip'],
            'featured_neighbourhoods': data['featured_neighbourhoods'],
            'neighbourhoods': data['neighbourhoods'],
            'neighbourhood_count': len(data['neighbourhoods']),
        })
    return guide
