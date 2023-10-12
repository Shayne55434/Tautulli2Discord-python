import requests
import json
import unicodedata
from datetime import datetime
import os

def main():
    def load_config():
        with open(config_path, 'r') as config_file:
            return json.load(config_file)
    
    def get_tmdb_info(tmdb_api_key, media_type, tmdb_id=None, title=None, year=None):
        # If TMDB ID found in Tautulli, use it to lookup the media information
        if tmdb_id != None:
            media_url = f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}?api_key={tmdb_api_key}&language=en-US"
            media_results = requests.get(media_url).json()
            if "success" in media_results and media_results["success"] is False:
                # If TMDB ID lookup returns no data, return None
                return None
            return media_results
        # No TMDB ID, so we will attempt to search TMDB for the media information
        else:
            tmdb_url = f"https://api.themoviedb.org/3/search/{media_type}?api_key={tmdb_api_key}&language=en-US&page=1&include_adult=false&query={title}"
            if year is not None and year != '':
                tmdb_url += f"&year={year}"
            
            tmdb_results = requests.get(tmdb_url).json()
            # Check if 'results' key exists and the list is not empty
            if 'results' in tmdb_results and len(tmdb_results['results']) > 0:
                # Get the first TMDB ID from the search results
                media_id = tmdb_results['results'][0]['id']
                media_url = f"https://api.themoviedb.org/3/{media_type}/{media_id}?api_key={tmdb_api_key}&language=en-US"
                media_results = requests.get(media_url).json()
                return media_results
        
        return None
    
    def get_sanitized_string(input_string):
        # Replace any non-ASCII characters with their closest ASCII representation
        normalized_string = unicodedata.normalize('NFKD', input_string).encode('ASCII', 'ignore').decode('utf-8')
        
        # Remove any remaining unwanted characters
        replace_values = {':': ''}
        for key, value in replace_values.items():
            normalized_string = normalized_string.replace(key, value)
        
        return normalized_string
    
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
    stream_log_path = os.path.join(script_directory, 'StreamLog.txt')
    
    # Parse the config file and assign variables
    config = load_config()
    script_name = 'CurrentStreams'
    script_settings = config['ScriptSettings'][script_name]
    discord_webhook = script_settings['Webhook']
    tautulli_url = config['Tautulli']['Url']
    tautulli_api_key = config['Tautulli']['APIKey']
    tmdb_api_key = config['TMDB']['APIKey']
    
    # Get PMS Identifier
    response = requests.get(f"{tautulli_url}/api/v2", params={"apikey": tautulli_api_key, "cmd": "get_server_info"})
    plex_server_identifier = response.json()["response"]["data"]["pms_identifier"]
    
    # Attempt to get Plex activity from Tautulli
    try:
        activity_url = f"{tautulli_url}/api/v2?apikey={tautulli_api_key}&cmd=get_activity"
        response = requests.get(activity_url)
        current_activity = response.json()
        sessions = current_activity['response']['data']['sessions']
    except Exception as e:
        payload = {
            'username': 'Current Streams',
            'content': f'**Could not get current streams from Tautulli.**\nError message:\n{e}'
        }
        push_to_discord(discord_webhook, payload)
        exit()

    # Loop through each stream
    sessions_embed = []
    for stream in sessions:
        sanitized_title = get_sanitized_string(stream['title'])
        tmdb_id = None
        
        # TV
        if stream['media_type'] == 'episode':
            tmdb_guid = next((guid for guid in stream['grandparent_guids'] if guid.startswith("tmdb://")), None)
            
            if tmdb_guid:
                # Extract the TMDB ID from the TMDB GUID
                tmdb_id = tmdb_guid.split("tmdb://")[1]
            
            sanitized_full_title = stream['full_title'] # "<Show Name> - <Episode Name>"
            tmdb_tv_results = get_tmdb_info(tmdb_api_key, 'tv', tmdb_id, sanitized_title, stream['year'])
            
            # Base embed parameters for TV
            embed_params = {
                'color': 40635,
                'title': sanitized_full_title,
                'author': {
                    'name': 'Open on Plex',
                    'url': f'https://app.plex.tv/desktop/#!/server/{plex_server_identifier}/details?key=%2Flibrary%2Fmetadata%2F{stream["grandparent_rating_key"]}',
                    'icon_url': 'https://i.imgur.com/FNoiYXP.png'
                },
                'description': get_sanitized_string(stream['summary']),
                'fields': [
                    {'name': 'User', 'value': stream['friendly_name'], 'inline': False},
                    {'name': 'Season', 'value': stream['parent_media_index'], 'inline': True},
                    {'name': 'Episode', 'value': stream['media_index'], 'inline': True}
                ],
                'footer': {'text': f'{stream["state"]} - {stream["progress_percent"]}%'},
                'timestamp': datetime.utcnow().isoformat()
            }
            
            if tmdb_tv_results:
                print(stream["title"], ' - Has TMdB results.')
                # Add TV-specific fields if TMDB results are available
                embed_params['url'] = f'https://www.themoviedb.org/tv/{tmdb_id}'
                embed_params['thumbnail'] = {'url': f'https://image.tmdb.org/t/p/w500{tmdb_tv_results["poster_path"]}'}
            else:
                print(stream["title"], ' - Does not have TMdB results. tmdb_id:', tmdb_id)
        
        # MOVIE
        elif stream['media_type'] == 'movie':
            tmdb_guid = next((guid for guid in stream['guids'] if guid.startswith("tmdb://")), None)
            
            if tmdb_guid:
                # Extract the TMDB ID from the TMDB GUID
                tmdb_id = tmdb_guid.split("tmdb://")[1]
            
            tmdb_movie_results = get_tmdb_info(tmdb_api_key, 'movie', tmdb_id, sanitized_title, stream['year'])
            
            # Base embed parameters for MOVIE
            embed_params = {
                'color': 13400320,
                'title': sanitized_title,
                'author': {
                    'name': 'Open on Plex',
                    'url': f'https://app.plex.tv/desktop/#!/server/{plex_server_identifier}/details?key=%2Flibrary%2Fmetadata%2F{stream["rating_key"]}',
                    'icon_url': 'https://i.imgur.com/FNoiYXP.png'
                },
                'description': get_sanitized_string(stream['summary']),
                'fields': [
                    {'name': 'User', 'value': stream['friendly_name'], 'inline': False},
                    {'name': 'Resolution', 'value': stream['stream_video_full_resolution'], 'inline': True},
                    {'name': 'Direct Play/Transcode', 'value': stream['transcode_decision'], 'inline': True}
                ],
                'footer': {'text': f'{stream["state"]} - {stream["progress_percent"]}%'},
                'timestamp': datetime.utcnow().isoformat()
            }
            
            if tmdb_movie_results:
                print(stream["title"], ' - Has TMdB results.')
                # Add MOVIE-specific fields if TMDB results are available
                embed_params['url'] = f'https://www.themoviedb.org/movie/{tmdb_id}'
                embed_params['thumbnail'] = {'url': f'https://image.tmdb.org/t/p/w500{tmdb_movie_results["poster_path"]}'}
            else:
                print(stream["title"], ' - Does not have TMdB results. tmdb_id:', tmdb_id)
        
        # MUSIC
        elif stream['media_type'] == 'track':
            embed_params = {
                'color': 3066993,
                'title': sanitized_title,
                'author': {
                    'name': 'Open on Plex',
                    'url': f'https://app.plex.tv/desktop/#!/server/{plex_server_identifier}/details?key=%2Flibrary%2Fmetadata%2F{stream["rating_key"]}',
                    'icon_url': 'https://i.imgur.com/FNoiYXP.png'
                },
                'description': get_sanitized_string(stream['summary']),
                'fields': [
                    {'name': 'User', 'value': stream['friendly_name'], 'inline': False},
                    {'name': 'Album', 'value': stream['parent_title'], 'inline': True},
                    {'name': 'Track', 'value': stream['media_index'], 'inline': True}
                ],
                'footer': {'text': f'{stream["state"]} - {stream["progress_percent"]}%'},
                'timestamp': datetime.utcnow().isoformat()
            }
        
        # Add line results to final object
        sessions_embed.append(embed_params)
    
    # If there are no sessions, make a new payload stating so
    if len(sessions) == 0:
        payload = {
            'embeds': [
                {
                    'color': 15158332,
                    'title': 'Nothing is currently streaming',
                    'timestamp': datetime.utcnow().isoformat()
                }
            ]
        }
    else:
        payload = {
            'username': 'Current Streams',
            'content': '**Current Streams on Plex:**',
            'embeds': sessions_embed
        }
    
    # Check if the log file exists, create it if not, and populate it with a filler value
    if not os.path.exists(stream_log_path):
        with open(stream_log_path, 'w') as log_file:
            log_file.write('-1')
    
    # Get the last stream count and then update the file with the current
    with open(stream_log_path, 'r+') as log_file:
        last_stream_count = int(log_file.read())
        log_file.seek(0)
        log_file.truncate()
        log_file.write(str(len(sessions)))
    
    if last_stream_count == 0 and len(sessions) == 0:
        # Log file and current stream count are both 0. Do not update.
        print('Nothing to update.')
    else:
        push_to_discord(discord_webhook, payload)

# Call the main function
if __name__ == "__main__":
    main()