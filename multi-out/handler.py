import json
import os
import logging
import requests

CDMI_PATH = '/cdmi'
CDMI_HEADERS = {
    'X-CDMI-Specification-Version': '1.1.1',
    'Content-Type': 'application/cdmi-object'
}
SPACES_PATH = '/api/v3/oneprovider/spaces/'
ATTRIBUTES_PATH = '/api/v3/oneprovider/attributes/'


def get_config():
    """Return a dict with the required environment variables"""
    config = {}
    config['ONEPROVIDER_HOST'] = os.environ.get('ONEPROVIDER_HOST').strip('/')
    config['ONEPROVIDER_TOKEN'] = os.environ.get('ONEPROVIDER_TOKEN').strip('/')
    config['ONEDATA_SPACE'] = os.environ.get('ONEDATA_SPACE').strip('/')
    config['HEADER'] = {'X-Auth-Token': config['ONEPROVIDER_TOKEN']}
    config['FOLDERS'] = get_config_folders()
    return config


def get_config_folders():
    """Read folder config from environment"""
    folders = []
    for env_key, env_val in os.environ.items():
        if env_key.startswith('FOLDER_'):
            folder_id = env_key.split('_', 1)[1]
            folder_name = env_val
            folder_extension = os.getenv(f'EXTENSION_{folder_id}')
            if folder_extension:
                folders.append({
                    'name': folder_name,
                    'extension': folder_extension
                })
    return folders


def check_space(config):
    """Checks if the configured space exists in Oneprovider"""
    space_url = 'https://{0}{1}'.format(
        config['ONEPROVIDER_HOST'],
        SPACES_PATH
    )
    r = requests.get(space_url, headers=config['HEADER'])
    if r.status_code == 200:
        spaces = r.json()
        space_names = []
        for space in spaces:
            space_names.append(space['name'])
        if config['ONEDATA_SPACE'] not in space_names:
            raise Exception(f'The space {0} does not exist'.format(
                config['ONEDATA_SPACE']
            ))
    elif r.status_code == 402:
        raise Exception('Invalid token')
    else:
        raise Exception('Error connecting to provider host')


def check_folders(config):
    """Checks if the specified folders exists in Onedata space"""
    for folder in config['FOLDERS']:
        folder_url = 'https://{0}{1}{2}/{3}'.format(
            config['ONEPROVIDER_HOST'],
            ATTRIBUTES_PATH,
            config['ONEDATA_SPACE'],
            folder['name']
        )
        r = requests.get(folder_url, headers=config['HEADER'])
        if r.status_code == 404:
            raise Exception('The folder {0} does not exist'.format(
                folder['name']
            ))


def process_event(event):
    """Checks if the event is valid (comes from OneTrigger) and returns the
    file path"""
    try:
        event = json.loads(event)
    except Exception as e:
        raise Exception(f'Invalid event format: {e}')
    if ('Records' in event and
            event['Records'] and
            'eventSource' in event['Records'][0] and
            event['Records'][0]['eventSource'] == 'OneTrigger'):
        return event['Key']
    else:
        raise Exception('Event is not generated by OneTrigger')


def process_file(file_path, config):
    """Checks if event file has a valid extension and copies it to the
    appropiate folder"""
    file_name = os.path.basename(file_path)
    for folder in config['FOLDERS']:
        if file_name.endswith(folder['extension']):
            file_url = 'https://{0}{1}/{2}/{3}/{4}'.format(
                config['ONEPROVIDER_HOST'],
                CDMI_PATH,
                config['ONEDATA_SPACE'],
                folder['name'],
                file_name
            )
            headers = {**CDMI_HEADERS, **config['HEADER']}
            body = {'copy': file_path}
            r = requests.put(file_url, headers=headers, json=body)
            if r.status_code in [201, 202]:
                msg = 'The file "{0}" has been copied to folder "{1}"'.format(
                    file_name,
                    folder['name']
                )
                logging.info(msg)
                return msg
            else:
                raise Exception('Error copying file')
    return 'The file "{0}" does not match with any specified extension'.format(
        file_name
    )


def handle(req):
    """Handle function"""
    try:
        # Get configuration
        config = get_config()
        # Ensure that the defined space exists
        check_space(config)
        # Check if defined folders exists
        check_folders(config)
        # Get the file from event
        file_path = process_event(req)
        # Process the file
        return process_file(file_path, config)
    except Exception as e:
        logging.error(e)
        return e
