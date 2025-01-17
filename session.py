import json
import subprocess
import sys
import urllib
from typing import Dict
from selenium import webdriver
import click
import requests

from src.common import aws
from src.common.config import ENVIRONMENT_LIST


@click.command()
@click.option('--env', required=True, type=click.Choice(ENVIRONMENT_LIST))
@click.option('-d', '--duration',  default=14400)
@click.option('-p', '--profile', 'profile', default=None)
def cli(env, duration, profile):
    """ Persist the temporary AWS access key, secret key and session token in the user ~/.aws/credentials..\n

    Examples:\n
        $ hatch session --env staging --profile aws-staging-dev
        $ hatch session --env tools
    """
    if not profile:
        profile = env

    creds = aws.request_credentials(env, duration)

    aws_configure(profile, dict(
        aws_access_key_id=creds.access_key_id,
        aws_secret_access_key=creds.secret_access_key,
        aws_session_token=creds.session_token
    ))

    request_url = login_link(creds)

    # Step 3: Format resulting temporary credentials into JSON
    url_credentials = {}
    url_credentials['sessionId'] = creds.access_key_id
    url_credentials['sessionKey'] = creds.secret_access_key
    url_credentials['sessionToken'] = creds.session_token
    json_string_with_temp_credentials = json.dumps(url_credentials)

    # Step 4. Make request to AWS federation endpoint to get sign-in token. Construct the parameter string with
    # the sign-in action request, a 12-hour session duration, and the JSON document with temporary credentials
    # as parameters.
    request_parameters = {}
    request_parameters['Action'] = 'getSigninToken'
    request_parameters['SessionDuration'] = '43200'
    request_parameters['Session'] = json_string_with_temp_credentials

    request_url = "https://signin.aws.amazon.com/federation"
    r = requests.post(request_url, data=request_parameters)

    # Returns a JSON document with a single element named SigninToken.
    signin_token = json.loads(r.text)

    # Step 5: Create a POST request where users can use the sign-in token to sign in to
    # the console. The POST request must be made within 15 minutes after the
    # sign-in token was issued.
    request_parameters = {}
    request_parameters['Action'] = 'login'
    request_parameters['Issuer'] = 'Example.org'
    request_parameters['Destination'] = 'https://console.aws.amazon.com/' # https://us-west-2.console.aws.amazon.com/elasticmapreduce/home?region=us-west-2#cluster-list:
    request_parameters['SigninToken'] = signin_token['SigninToken']

    jsrequest = '''
    var form = document.createElement('form');
    form.method = 'POST';
    form.action = '{request_url}';
    request_parameters = {request_parameters}
    for (var param in request_parameters) {{
        if (request_parameters.hasOwnProperty(param)) {{
            const hiddenField = document.createElement('input');
            hiddenField.type = 'hidden';
            hiddenField.name = param;
            hiddenField.value = request_parameters[param];
            form.appendChild(hiddenField);
        }}
    }}
    document.body.appendChild(form);
    form.submit();
    '''.format(request_url=request_url, request_parameters=request_parameters)

    chrome_options = webdriver.ChromeOptions()

    # Keeps the browser open
    chrome_options.add_experimental_option("detach", True)

    # Browser is displayed in a custom window size
    chrome_options.add_argument("window-size=1500,1000")

    # Removes the "This is being controlled by automation" alert / notification
    chrome_options.add_experimental_option("excludeSwitches", ['enable-automation'])


    driver = webdriver.Chrome(options=chrome_options)
    driver.execute_script(jsrequest);

    # Send final URL to stdout
    print(request_url)

    print(f"Token has been refreshed for the AWS profile {profile}, it will expire on {creds.expiration_date}")


def login_link(creds):
    url_credentials = {}
    url_credentials['sessionId'] = creds.access_key_id
    url_credentials['sessionKey'] = creds.secret_access_key
    url_credentials['sessionToken'] = creds.session_token
    json_string_with_temp_credentials = json.dumps(url_credentials)
    request_parameters = "?Action=getSigninToken"
    request_parameters += "&SessionDuration=43200"
    if sys.version_info[0] < 3:
        def quote_plus_function(s):
            return urllib.quote_plus(s)
    else:
        def quote_plus_function(s):
            return urllib.parse.quote_plus(s)
    request_parameters += "&Session=" + quote_plus_function(json_string_with_temp_credentials)
    request_url = "https://signin.aws.amazon.com/federation" + request_parameters
    r = requests.get(request_url)
    # Returns a JSON document with a single element named SigninToken.
    signin_token = json.loads(r.text)
    # Step 5: Create URL where users can use the sign-in token to sign in to
    # the console. This URL must be used within 15 minutes after the
    # sign-in token was issued.
    request_parameters = "?Action=login"
    request_parameters += "&Issuer=Example.org"
    request_parameters += "&Destination=" + quote_plus_function("https://console.aws.amazon.com/")
    request_parameters += "&SigninToken=" + signin_token["SigninToken"]
    request_url = "https://signin.aws.amazon.com/federation" + request_parameters
    return request_url


def aws_configure(profile: str, params: Dict[str, str]):
    for k, v in params.items():
        result = subprocess.run(f"aws configure set {k} {v} --profile {profile}", shell=True)
        if result.returncode != 0:
            raise Exception(f"AWS configure command failed: {result.stderr.decode('utf-8').strip() if result.stderr else None}")
