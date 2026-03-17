import requests

response = requests.get('https://arqstorecekid.vercel.app/api/game')

if response.status_code == 200:
    data = response.json()
    for game in data['data']:
        print(game['name'], game['slug'], game['endpoint'])
else:
    print('Failed to retrieve data')