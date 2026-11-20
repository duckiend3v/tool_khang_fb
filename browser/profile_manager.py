import os
import shutil

class ProfileManager:
    def __init__(self):
        self.base_path = os.path.join(os.getcwd(), 'data', 'profiles')

    def get_profile_path(self, platform, account_id):
        path = os.path.join(self.base_path, platform, account_id)
        if not os.path.exists(path):
            os.makedirs(path)
        return path

    def delete_profile(self, platform, account_id):
        path = os.path.join(self.base_path, platform, account_id)
        if os.path.exists(path):
            try:
                shutil.rmtree(path)
                return True
            except Exception as e:
                print(f"Lỗi xóa profile: {e}")
                return False
        return False