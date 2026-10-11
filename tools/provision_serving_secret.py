"""One-time secret-version add. Never prints, writes or artifacts credentials."""
import base64,os
import google.auth
from google.auth.transport.requests import AuthorizedSession
credentials,_=google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
key=os.environ['MOTOMEDIC_GEMINI_API_KEY']
if not key or len(key)>1000: raise RuntimeError('Provider secret missing or invalid')
session=AuthorizedSession(credentials)
response=session.post('https://secretmanager.googleapis.com/v1/projects/motomedic-ai-20261009/secrets/motomedic-gemini-serving-v1:addVersion',
    json={'payload':{'data':base64.b64encode(key.encode()).decode()}},timeout=25)
if response.status_code!=200: raise RuntimeError('Secret write failed with HTTP '+str(response.status_code))
name=response.json()['name']
assert name.startswith('projects/279945185781/secrets/motomedic-gemini-serving-v1/versions/')
print('Provider secret version provisioned: '+name)
