#!/usr/bin/env python3
"""
Test script to call the job_status function directly
"""
import sys
import os
import json
from unittest.mock import Mock

# Add the api directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'api'))

# Load real credentials from local.settings.json
with open('api/local.settings.json', 'r') as f:
    settings = json.load(f)

# Set environment variables for local testing
os.environ['DRY_RUN'] = settings['Values'].get('DRY_RUN', 'false')
os.environ['AZURE_SUBSCRIPTION_ID'] = settings['Values']['AZURE_SUBSCRIPTION_ID']
os.environ['AZURE_RESOURCE_GROUP'] = settings['Values']['AZURE_RESOURCE_GROUP']
os.environ['AZURE_CLIENT_ID'] = settings['Values']['AZURE_CLIENT_ID']
os.environ['AZURE_CLIENT_SECRET'] = settings['Values']['AZURE_CLIENT_SECRET']
os.environ['AZURE_TENANT_ID'] = settings['Values']['AZURE_TENANT_ID']
os.environ['SSH_PUBLIC_KEY'] = settings['Values']['SSH_PUBLIC_KEY']
os.environ['SSH_PRIVATE_KEY'] = settings['Values']['SSH_PRIVATE_KEY']

# Import the function
from api.job_status.__init__ import main

# Mock HTTP request
class MockHttpRequest:
    def __init__(self, params=None):
        self.params = params or {}
        self.headers = {}

    def params(self):
        return self.params

# Create a mock request with the operation ID
req = MockHttpRequest()
req.params = {'id': 'wg-1761572759'}

# Call the function
print('Testing job_status function directly...')
try:
    response = main(req)
    print(f'Status Code: {response.status_code}')
    print(f'Response Body: {response.get_body().decode("utf-8")}')
    print(f'Headers: {dict(response.headers)}')
except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()
