import requests

BASE = 'http://127.0.0.1:8000/api'

def login(username, password):
    r = requests.post(f'{BASE}/accounts/login/', json={'username': username, 'password': password})
    r.raise_for_status()
    return r.json()['access']

def auth(token):
    return {'Authorization': f'Bearer {token}'}

student_token = login('rahul_student', 'StudentPass123!')
print('student login ok')

issuers = requests.get(f'{BASE}/issuers/', headers=auth(student_token)).json()
print('issuers:', issuers)

# upload a doc as AADHAAR (college allowed type)
files = {'file': ('test.txt', b'hello world aadhaar test', 'text/plain')}
data = {'doc_type': 'AADHAAR', 'title': 'My Aadhaar test'}
r = requests.post(f'{BASE}/documents/upload/', headers=auth(student_token), data=data, files=files)
print('upload status', r.status_code, r.json())
doc = r.json()
doc_id = doc['id']

# find college issuer
college = next(i for i in (issuers.get('results') or issuers) if i['issuer_type'] == 'COLLEGE')
print('college issuer', college)

r = requests.post(f'{BASE}/documents/{doc_id}/request-verification/', headers=auth(student_token), json={'issuer': college['id']})
print('request-verification status', r.status_code, r.json())

college_token = login('college_staff', 'CollegePass123!')
print('college login ok')

r = requests.get(f'{BASE}/documents/?status=PENDING', headers=auth(college_token))
print('pending list status', r.status_code)
print(r.json())
