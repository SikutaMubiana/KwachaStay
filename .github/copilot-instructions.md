# KwachaStay AI coding instructions

## Project shape
- This is a Flask app with one main entry point in `app.py`; database access is centralized through `get_db()` and `@app.before_request` loads the current user from `session`.
- `database.py` is the runtime adapter: SQLite when `DATABASE_URL` is empty, PostgreSQL (Supabase) when it is set. Keep route SQL portable and let the adapter translate `?` placeholders and SQLite helpers.
- The canonical data model lives in `schema.sql`: `users`, `properties`, `property_images`, `reviews`, `bookings`, `messages`, `wishlists`, `availability`, `payout_methods`.
- UI is server-rendered Jinja templates under `templates/`; most pages extend `base.html` and use Tailwind-style utility classes.
- The app is a single-service marketplace: listings, booking flow, dashboard, admin actions, notifications, and profile logic all live in `app.py`, not a separate API/backend split.

## Important app flows
- Homepage/search behavior is in `index()`; it supports keyword search, compound filter, price filter, property type, amenity flags, and sorting in one query.
- Listing creation is `add_house()` and owner edits are in `edit_house()`; both write to `properties` and `property_images`.
- Booking flow is driven by `checkout()`, `booking_receipt()`, and dashboard approval actions (`booking/approve`, `booking/decline`, `booking/cancel`).
- Admin features live behind `admin_required()` and are routed through `/admin` actions like verification, bans, and forced delist/relist.
- Messaging and notifications are part of the core user experience; the app creates notification rows from route logic instead of a dedicated service layer.

## Patterns to follow
- Prefer adding logic to the existing Flask route/controller style instead of introducing a separate framework or service layer.
- Reuse `g.user` and `session['user_id']` for auth state; access control is route-based (`@login_required`, `@admin_required`).
- Database mutations usually run in a single SQLite transaction with `db.execute(...)` + `db.commit()`.
- For property cards, fetch related images/reviews inline in the route and pass the prepared dicts into the template; templates expect fields like `property.images`, `property.rating`, `owner_name`, etc.

## Frontend conventions
- Keep templates in `templates/*.html`; use the same Tailwind utility styling and existing form patterns for buttons, cards, and tabs.
- Input validation is often done in the route, not by JS-only rules.
- `dashboard.html` is the primary pattern for role-based sections and action forms; match its tabbed layout when adding new account features.

## Workflow and environment
- Local dev entry point: `python app.py` from the project root; the app initializes the SQLite database automatically if `kwachastay.db` does not exist.
- App config relies on `.env` variables for `SECRET_KEY`, email SMTP settings, and Flutterwave keys (`FLUTTERWAVE_PUBLIC_KEY`, `FLUTTERWAVE_SECRET_KEY`).
- `reset_db.py` wipes the database for a clean slate; `migrate_*.py` files are versioned schema updates and should be respected when changing the schema.
- The project currently has no dedicated test suite; validate changes by running the app locally and exercising the affected route/template flow.

## Product-specific guidance
- Lusaka market context matters: listings use compounds/neighbourhoods such as Kabulonga, Rhodes Park, Woodlands, etc., and filters should respect that vocabulary.
- The app already models “hostel / hotel / guest house / villa / house / apartment” listings and a verified flag; keep those as first-class concepts.
- Keep price semantics aligned with the existing schema: `price_per_night` and `price_period` are used across search, dashboard, and booking screens.
- For new features, prefer server-side filtering and route-driven actions over a frontend-only implementation.
