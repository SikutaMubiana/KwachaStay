import os

from werkzeug.utils import secure_filename


class LocalUploadStorage:
    def __init__(self, upload_folder):
        self.upload_folder = os.path.abspath(upload_folder)

    def save(self, uploaded_file, filename):
        safe_name = secure_filename(filename)
        if not safe_name:
            raise ValueError('A safe upload filename is required.')
        os.makedirs(self.upload_folder, exist_ok=True)
        path = os.path.abspath(os.path.join(self.upload_folder, safe_name))
        if os.path.commonpath((self.upload_folder, path)) != self.upload_folder:
            raise ValueError('Upload path is outside the configured storage directory.')
        uploaded_file.save(path)
        return path

    def delete(self, path):
        resolved_path = os.path.abspath(path)
        if os.path.commonpath((self.upload_folder, resolved_path)) != self.upload_folder:
            raise ValueError('Upload path is outside the configured storage directory.')
        os.remove(resolved_path)
