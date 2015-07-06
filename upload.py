import json
import os
import time
import webbrowser
import urllib
import requests
from requests_oauthlib import OAuth2Session
from flask import Flask, request

# config
PORT = int(os.environ.get('PORT', 8000))
PLAYLIST_NAME = os.environ.get('PLAYLIST_NAME', 'gopro')
TOKEN_FILENAME = os.environ.get('TOKEN_FILENAME', '.token')
PLAYLIST_FILENAME = os.environ.get('PLAYLIST_FILENAME', '.playlist')
CLIENT_ID = os.environ['YOUTUBE_CLIENT_ID']
CLIENT_SECRET = os.environ['YOUTUBE_CLIENT_SECRET']

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/auth"
GOOGLE_TOKEN_URL = "https://accounts.google.com/o/oauth2/token"

def get_code():
    "Open a web browser to go through the google oauth round trip"
    params = {
        'client_id': CLIENT_ID,
        'redirect_uri': 'http://localhost:{}/oauth/callback'.format(PORT),
        'scope': 'https://www.googleapis.com/auth/youtube',
        'response_type': 'code',
        'access_type': 'offline',
    }
    webbrowser.open('{}?{}'.format(GOOGLE_AUTH_URL, urllib.urlencode(params)))

def get_token(code):
    "Exchange an oauth code for an access token"
    data = {
        'code': code,
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'redirect_uri': 'http://localhost:{}/oauth/callback'.format(PORT),
        'grant_type': 'authorization_code',
    }
    r = requests.post(GOOGLE_TOKEN_URL, data=data)
    r.raise_for_status()
    token = r.json()
    if 'expires_in' in token:
        # expires_in (relative) is of no use. Replace with expires_at.
        token['expires_at'] = int(time.time()) + token.pop('expires_in')
    return token

def token_refreshed(token):
    "Update the token file with the refreshed access token"
    with open(TOKEN_FILENAME, 'w') as f:
        f.write(json.dumps(token))

def get_playlist_id(session):
    "Get or create playlist"
    if os.path.exists(PLAYLIST_FILENAME):
        with open(PLAYLIST_FILENAME, 'r') as f:
            return f.read()

    r = session.get('https://www.googleapis.com/youtube/v3/playlists', params={
        'part': ','.join(('snippet', 'id')),
        'mine': 'true',
    })
    r.raise_for_status()
    for item in r.json()['items']:
        if item['snippet']['title'] == PLAYLIST_NAME:
            playlist_id = item['id']
    else:
        # playlist not found, create it
        r = session.post('https://www.googleapis.com/youtube/v3/playlists', params={
            'part': 'snippet',
        }, json={
            'kind': 'youtube#playlist',
            'snippet': {
                'title': PLAYLIST_NAME,
            },
        })
        r.raise_for_status()
        playlist_id = r.json()['id']

    with open(PLAYLIST_FILENAME, 'w') as f:
        f.write(playlist_id)

    return playlist_id

def get_session():
    "Get an oauth 2 authenticated requests session"
    with open(TOKEN_FILENAME, 'r') as f:
        token = json.loads(f.read())
    return OAuth2Session(CLIENT_ID,
                         token=token,
                         auto_refresh_kwargs={
                             'client_id': CLIENT_ID,
                             'client_secret': CLIENT_SECRET,
                         },
                         auto_refresh_url=GOOGLE_TOKEN_URL,
                         token_updater=token_refreshed)

def update_playlist():
    session = get_session()
    playlist_id = get_playlist_id(session)

if __name__ == '__main__':
    if not os.path.exists(TOKEN_FILENAME):
        app = Flask(__name__)

        @app.route("/oauth/callback")
        def oauth_callback():
            token = get_token(request.args['code'])
            with open(TOKEN_FILENAME, 'w') as f:
                f.write(json.dumps(token))
            request.environ.get('werkzeug.server.shutdown')()
            return 'Auth complete. Close your web browser'

        app.config['SERVER_NAME'] = 'localhost:{}'.format(PORT)
        get_code()
        app.run()
    else:
        update_playlist()
