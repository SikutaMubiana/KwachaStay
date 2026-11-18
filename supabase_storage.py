"""Supabase Storage adapter for user-uploaded listing images.

The service-role key must only be set in the server environment. Never expose it
to browser code or commit it to source control.
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

from werkzeug.utils import secure_filename


class SupabaseUploadStorage:
    def __init__(self, url=None, service_role_key=None, bucket=None):
        self.url = (url or os.getenv('SUPABASE_URL', '')).rstrip('/')
        self.service_role_key = service_role_key or os.getenv('SUPABASE_SERVICE_ROLE_KEY', '')
        self.bucket = bucket or os.getenv('SUPABASE_STORAGE_BUCKET', 'property-images')
        if not self.url or not self.service_role_key or not self.bucket:
            raise ValueError('Supabase Storage requires SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, and SUPABASE_STORAGE_BUCKET.')

    def _request(self, method, path, data=None, content_type=None):
        headers = {
            'Authorization': f'Bearer {self.service_role_key}',
            'apikey': self.service_role_key,
        }
        if content_type:
            headers['Content-Type'] = content_type
        request = urllib.request.Request(f'{self.url}{path}', data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            raise RuntimeError(f'Supabase Storage request failed with HTTP {error.code}.') from error
        except urllib.error.URLError as error:
            raise RuntimeError('Supabase Storage could not be reached.') from error

    def save(self, uploaded_file, filename):
        safe_name = secure_filename(filename)
        if not safe_name:
            raise ValueError('A safe upload filename is required.')
        data = uploaded_file.read()
        if hasattr(uploaded_file, 'seek'):
            uploaded_file.seek(0)
        encoded_bucket = urllib.parse.quote(self.bucket, safe='')
        encoded_name = urllib.parse.quote(safe_name, safe='/')
        self._request(
            'POST',
            f'/storage/v1/object/{encoded_bucket}/{encoded_name}',
            data=data,
            content_type=getattr(uploaded_file, 'mimetype', None) or 'application/octet-stream',
        )
        return f'{self.url}/storage/v1/object/public/{encoded_bucket}/{encoded_name}'

    def delete(self, path):
        prefix = f'{self.url}/storage/v1/object/public/{urllib.parse.quote(self.bucket, safe="")}/'
        if not path.startswith(prefix):
            raise ValueError('Upload path is outside the configured Supabase bucket.')
        name = path[len(prefix):]
        payload = json.dumps({'prefixes': [urllib.parse.unquote(name)]}).encode('utf-8')
        self._request(
            'DELETE',
            f'/storage/v1/object/{urllib.parse.quote(self.bucket, safe="")}',
            data=payload,
            content_type='application/json',
        )
