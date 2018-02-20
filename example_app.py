from flask import Flask, redirect, url_for, session, request, render_template
from jose import jws
import json, requests, uuid, yaml
from security.microsoft_client import microsoft_client
from security.user_operations import get_user

with open("config/config.yml", 'r') as ymlfile:
    config = yaml.load(ymlfile)

app = Flask(__name__)
app.debug = True
app.secret_key = 'development'

# This sample loads the keys on boot, but for production
# the keys should be refreshed either periodically or on
# jws.verify fail to be able to handle a key rollover
microsoft = microsoft_client(config, app)

@app.route('/')
@app.route('/login', methods = ['POST', 'GET'])
def login():
    if 'microsoft_token' in session:
        return redirect(url_for('me'))

    return _authenticate(session, microsoft)

@app.route('/logout', methods = ['POST', 'GET'])
def logout():
    session.pop('microsoft_token', None)
    session.pop('claims', None)
    session.pop('state', None)
    return redirect(url_for('index'))

@app.route('/login/authorized')
def authorized():
    _verify_state(session, request)
    response = microsoft.authorized_response()

    if response is None:
        return _access_denied_message(response)

    _store_results(session, response)
    return redirect(url_for('me'))

@app.route('/me')
def me():
    me = microsoft.get('me')
    data={'$select':config['user_attributes'], '$expand':'extensions'}
    user_identity = microsoft.get('me', data=data)

    return render_template('me.html', me=str(me.data), user_identity=user_identity.data)

# If library is having trouble with refresh, uncomment below and implement refresh handler
# see https://github.com/lepture/flask-oauthlib/issues/160 for instructions on how to do this
# Implements refresh token logic
# @app.route('/refresh', methods=['POST'])
# def refresh():

@microsoft.tokengetter
def get_microsoft_oauth_token():
    return session.get('microsoft_token')

if __name__ == '__main__':
    app.run()

def _authenticate(session, microsoft_client):
    session['state'] = uuid.uuid4()
    return microsoft_client.authorize(callback=url_for('authorized', _external=True), state=session['state'])

def _access_denied_message(request):
    return "Access Denied: Reason=%s\nError=%s" % (response.get('error'), request.get('error_description'))

def _verify_state(session, request):
    if str(session['state']) != str(request.args['state']):
        raise Exception('State has been tampered with, end authentication')

def _store_results(session, response):
    access_token = response['access_token']
    session['microsoft_token'] = (access_token, '')
