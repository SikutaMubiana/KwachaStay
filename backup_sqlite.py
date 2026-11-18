import argparse
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import zipfile


ROOT = Path(__file__).resolve().parent
DATABASE = ROOT / 'kwachastay.db'
UPLOADS = ROOT / 'static' / 'uploads'


def create_backup(destination):
    if not DATABASE.is_file():
        raise FileNotFoundError(f'SQLite database not found: {DATABASE}')

    destination.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    database_backup = destination / f'kwachastay-{stamp}.sqlite3'
    with closing(sqlite3.connect(DATABASE)) as source, closing(sqlite3.connect(database_backup)) as target:
        source.backup(target)

    photo_backup = None
    if UPLOADS.is_dir():
        photo_backup = destination / f'kwachastay-uploads-{stamp}.zip'
        with zipfile.ZipFile(photo_backup, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for path in UPLOADS.rglob('*'):
                if path.is_file():
                    archive.write(path, path.relative_to(UPLOADS))

    return database_backup, photo_backup


def main():
    parser = argparse.ArgumentParser(
        description='Create local SQLite and uploaded-photo backups. This does not back up Neon.'
    )
    parser.add_argument(
        '--destination',
        type=Path,
        default=ROOT / 'backups',
        help='Directory for private backup files (default: ./backups)',
    )
    args = parser.parse_args()
    database_backup, photo_backup = create_backup(args.destination.resolve())
    print(f'Database backup created: {database_backup}')
    if photo_backup:
        print(f'Uploaded photos backup created: {photo_backup}')
    else:
        print('No local uploads directory found; no photo archive created.')


if __name__ == '__main__':
    main()
