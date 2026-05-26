import requests

payload = {
    'to': '+2349157405905',
    'from': 'Afrixa',
    'sms': 'Test message from Python using the active Afrixa Sender ID!',
    'type': 'plain',
    'channel': 'generic',
    'api_key': 'TLiEjXSnBFrgsZmceRGCwoNqjveCzoUIJpKhMAGjWHODFNkeYhPSdcqINQaPaz'
}

print("Testing send SMS with 'Afrixa' as Sender ID...")
try:
    r = requests.post('https://api.termii.com/api/sms/send', json=payload, timeout=5)
    print("Status:", r.status_code)
    print("Response:", r.text)
except Exception as e:
    print("Error:", e)
