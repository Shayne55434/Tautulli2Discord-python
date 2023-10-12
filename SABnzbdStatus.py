import requests
import json
import os
from datetime import datetime

def main():
    def load_config():
        with open(config_path, 'r') as config_file:
            return json.load(config_file)
    
    def push_to_discord(discord_webhook, payload):
        headers = {'Content-Type': 'application/json'}
        try:
            response = requests.post(discord_webhook, json=payload, headers=headers)
            response.raise_for_status()
            print("Data sent to Discord successfully.")
        except requests.exceptions.RequestException as e:
            print(f"Error sending to Discord: {e}")
            print(f"Response content: {response.content}")
            print(payload)
    
    # Get the directory where the script is located
    script_directory = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_directory, 'config.json')
    log_file_path = os.path.join(script_directory, 'SABLog.txt')
    
    # Load configuration from the config.json file
    config = load_config()
    script_name = 'SABnzbdStatus'
    discord_webhook = config['ScriptSettings'][script_name]['Webhook']
    sabnzbd_url = config['SABnzbd']['Url']
    sabnzbd_api_key = config['SABnzbd']['APIKey']
    
    # Get SABnzbd queue information
    try:
        response = requests.get(f"{sabnzbd_url}/api?apikey={sabnzbd_api_key}&output=json&mode=queue")
        sabnzbd_queue = response.json()['queue']
    except Exception as e:
        payload = {
            'username': 'SABnzbdStatus',
            'content': f'**Could not get SABnzbd queue information.**\nError message:\n{e}'
        }
        push_to_discord(discord_webhook, payload)
        exit()
    
    # Ensure the log file exists. If not, create it.
    if not os.path.exists(log_file_path):
        with open(log_file_path, 'w') as log_file:
            log_file.write('-1')
    
    # Get the last last_log_value and then update the file with the current
    with open(log_file_path, 'r+') as log_file:
        last_log_value = int(log_file.read())
        log_file.seek(0)
        log_file.truncate()
        log_file.write(str(len(sabnzbd_queue['slots'])))
    
    slot_embed = []
    if sabnzbd_queue['paused']:
        if sabnzbd_queue['pause_int'] == '0':
            time_remaining = 'Unknown'
        else:
            time_remaining = sabnzbd_queue['pause_int'] + ' (m:ss)'
        
        embed_params = {
            'color': 15197440,
            'title': 'Downloads Paused',
            'description': 'Downloads are currently paused. Either this was manually done by the server admin, or automatically if there is no free space remaining.',
            'fields': [
                {'name': 'Time Left', 'value': time_remaining, 'inline': False},
                {'name': 'Free Space', 'value': f"{sabnzbd_queue['diskspace1']}GB", 'inline': True},
                {'name': 'Total Space', 'value': f"{sabnzbd_queue['diskspacetotal1']}GB", 'inline': True}
            ],
            'footer': {'text': 'Updated'},
            'timestamp': datetime.utcnow().isoformat()
        }
        slot_embed.append(embed_params)
        payload = {
            'username': 'Downloads Paused',
            'content': f"Downloading **{len(sabnzbd_queue['slots'])}** item(s) at **{sabnzbd_queue['speed']}**Bs/second. Time remaining: **{sabnzbd_queue['timeleft']}**",
            'embeds': slot_embed
        }
    elif len(sabnzbd_queue['slots']) > 0:
        for slot in sabnzbd_queue['slots'][:10]:
            embed_params = {
                'color': 15197440,
                'title': 'Filename',
                'description': slot['filename'],
                'fields': [
                    {'name': 'Completed', 'value': f"{slot['percentage']}%", 'inline': False},
                    {'name': 'Time Left', 'value': slot['timeleft'], 'inline': True},
                    {'name': 'Category', 'value': slot['cat'], 'inline': True},
                    {'name': 'File Size', 'value': slot['size'], 'inline': True}
                ],
                'footer': {'text': 'Updated'},
                'timestamp': datetime.utcnow().isoformat()
            }
            slot_embed.append(embed_params)
        
        payload = {
            'username': 'First 10 Downloads',
            'content': f"Downloading **{len(sabnzbd_queue['slots'])}** item(s) at **{sabnzbd_queue['speed']}**Bs/second. Time remaining: **{sabnzbd_queue['timeleft']}**",
            'embeds': slot_embed
        }
    else:
        embed_params = {
            'color': 15197440,
            'title': 'No downloads',
            'description': 'There is nothing currently in the download queue.',
            'fields': [
                {'name': 'Time Left', 'value': 'NA', 'inline': False},
                {'name': 'Free Space', 'value': f"{sabnzbd_queue['diskspace1']}GB", 'inline': True},
                {'name': 'Total Space', 'value': f"{sabnzbd_queue['diskspacetotal1']}GB", 'inline': True}
            ],
            'footer': {'text': 'Updated'},
            'timestamp': datetime.utcnow().isoformat()
        }
        slot_embed.append(embed_params)
        payload = {
            'username': 'No Downloads',
            'content': 'Nothing currently in the download queue.',
            'embeds': slot_embed
        }
    
    if last_log_value == 0 and len(sabnzbd_queue['slots']) == 0:
        # Log file and current slots are both 0. Do not update.
        print('Nothing to update.')
    else:
        push_to_discord(discord_webhook, payload)

if __name__ == "__main__":
    main()