import os
import sys
import json
from datetime import datetime

import boto3

from src.common import config
from src.common import credentials

config_root = config.config_root


def _cache_credentials_json(environment, credentials):
    try:
        with open(f'{config_root}/.hatch/{environment}-credentials.json', 'w') as file:
            file.write(json.dumps(credentials, sort_keys=True, indent=2))
    except Exception as ex:
        print(f"We couldn't cache your credentials in a file due to the following error: {str(ex)}")


def _convert_json_to_credentials(credentials_json):
    expiration = datetime.fromisoformat(credentials_json['Expiration'])
    return credentials.Credentials(
        access_key_id=credentials_json['AccessKeyId'],
        secret_access_key=credentials_json['SecretAccessKey'],
        session_token=credentials_json['SessionToken'],
        expiration_date=expiration)


def get_cached_credentials(environment):
    try:
        with open(f'{config_root}/.hatch/{environment}-credentials.json', 'r') as file:
            return _convert_json_to_credentials(json.loads(file.read()))
    except FileNotFoundError:
        return None


_last_token_code: str = "OLD_CODE"


def request_credentials(environment, duration_seconds=14400):
    configuration = config.Configuration()

    token_code = os.environ.get("AWS_TOKEN_CODE")
    if not token_code:
        sys.stderr.write('AWS MFA token: ')
        token_code = input()

        global _last_token_code
        if token_code == _last_token_code:
            print("\nThat code has already been used. Wait for another one.\n")
            token_code = input('AWS MFA token: ')

        _last_token_code = token_code

    client = boto3.client(
        'sts',
        aws_access_key_id=configuration.aws_access_key,
        aws_secret_access_key=configuration.aws_secret_access_key)

    response = client.assume_role(
        RoleArn=config.CREDENTIALS_MAP[environment],
        RoleSessionName='hatch-cli-session',
        SerialNumber=configuration.aws_mfa_serial,
        DurationSeconds=duration_seconds,
        TokenCode=token_code)

    credentials_json = response['Credentials']
    # We have to convert the expiration timestamp to string otherwise the
    # json module will fail to serialize it.
    credentials_json['Expiration'] = str(credentials_json['Expiration'])
    _cache_credentials_json(environment, credentials_json)
    return _convert_json_to_credentials(credentials_json)
