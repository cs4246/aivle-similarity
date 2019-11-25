import requests
import json
import os 
import urllib3
import shutil

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import settings

class BaseAPI(object):
    def __init__(self, auth=None, verify=False):
        self.session = requests.Session()
        self.session.auth = auth
        self.verify = verify
        
    def request(self, url, method='get', **kwargs):
        assert method in ['get', 'post', 'delete', 'put']
        response = getattr(self.session, method)(url, verify=self.verify, **kwargs)
        return response
        
    def download(self, url, filepath):
        response = self.session.get(url, stream=True)
        with open(filepath, 'wb') as out_file:
            shutil.copyfileobj(response.raw, out_file)
        return response
        
class API(BaseAPI):
    def __init__(self, base_url, auth=(settings.USERNAME, settings.PASSWORD)):
        super().__init__(auth=auth)
        self.base_url = base_url
        self.base = super()
        
    def request(self, id=None, action=None, method='get', **kwargs):
        assert method in ['get', 'post', 'delete', 'put']
        url = self.base_url
        if id: url += str(id) + '/'
        if action: url += format(action) + '/'
        return super().request(url, method=method, **kwargs)