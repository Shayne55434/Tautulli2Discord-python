import requests
import json
from datetime import datetime
import os

# Get the directory where the script is located
script_directory = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(script_directory, 'config.json')

# Load configuration from the config.json file
def load_config():
    with open(config_path, 'r') as config_file:
        return json.load(config_file)

def main():
    config = load_config()
    script_name = 'PlexLibraryStats'
    script_settings = config['ScriptSettings'][script_name]
    discord_webhook = script_settings['Webhook']
    excluded_libraries = script_settings['ExcludedLibraries']
    tautulli_url = config['Tautulli']['Url']
    tautulli_api_key = config['Tautulli']['APIKey']
    
    # Function to send data to Discord webhook
    def push_to_discord(payload):
        headers = {'Content-Type': 'application/json'}
        try:
            response = requests.post(discord_webhook, data=json.dumps(payload), headers=headers)
            response.raise_for_status()
            response.cookies
            print("Data sent to Discord successfully.")
        except requests.exceptions.RequestException as e:
            print(f"Error sending to Discord: {e}")
            print(f"Response content: {response.content}")
            print(payload)
    
    # Function to get library stats
    def get_library_stats(section_id):
        library_url = f"{tautulli_url}/api/v2?apikey={tautulli_api_key}&cmd=get_library_media_info&section_id={section_id}"
        response = requests.get(library_url)
        data = response.json()['response']['data']
        total_size_bytes = data['total_file_size']
        
        if total_size_bytes >= 1000000000000:
            size_format = 'Tb'
            formatted_size = round(total_size_bytes / 1e12, 2)
        else:
            size_format = 'Gb'
            formatted_size = round(total_size_bytes / 1e9, 2)
        
        return {
            'Size': formatted_size,
            'Format': size_format,
        }
    
    # Get library data from Tautulli
    libraries_table_url = f"{tautulli_url}/api/v2?apikey={tautulli_api_key}&cmd=get_libraries_table"
    response = requests.get(libraries_table_url)
    libraries_data = response.json()['response']['data']['data']
    
    # Filter out excluded libraries
    libraries_stats = []
    for library in libraries_data:
        if library['section_name'] not in excluded_libraries:
            stats = get_library_stats(library['section_id'])
            stats.update({'Library': library['section_name'], 'Type': library['section_type'], 'Count': library['count'], 'SeasonAlbumCount': library['parent_count'], 'EpisodeTrackCount': library['child_count']})
            libraries_stats.append(stats)
    
    # Group libraries by type (Movie, TV, Music) and format data for Discord payload
    discord_payload = []
    for lib_type in ['movie', 'show', 'artist']:
        libraries_by_type = [lib for lib in libraries_stats if lib['Type'] == lib_type]
        if libraries_by_type:
            type_title = f"{lib_type.capitalize()} Libraries"
            type_color = {'movie': 13400320, 'show': 40635, 'artist': 39270}[lib_type]
            
            type_payload = {
                    'title': type_title,
                    'color': type_color,
                    "timestamp": datetime.utcnow().isoformat(),
                    'fields': []
            }
        
        for lib in libraries_by_type:
            field_data = [
                {'name': 'Library', 'value': lib['Library'], 'inline': False},  # Change 'inline' to False
                {'name': 'Count', 'value': lib['Count'], 'inline': True},
                {'name': 'Size', 'value': f"{lib['Size']} {lib['Format']}", 'inline': True},
            ] 
            # If it's a TV library, add Seasons and Episodes to the field data
            if lib_type == 'show':
                field_data.extend([
                    {'name': 'Seasons', 'value': lib['SeasonAlbumCount'], 'inline': True},
                    {'name': 'Episodes', 'value': lib['EpisodeTrackCount'], 'inline': True},
                ])
            # If it's a Music library, add Albums and Tracks to the field data
            elif lib_type == 'artist':
                field_data.extend([
                    {'name': 'Albums', 'value': lib['SeasonAlbumCount'], 'inline': True},
                    {'name': 'Tracks', 'value': lib['EpisodeTrackCount'], 'inline': True},
                ]) 
            type_payload['fields'].extend(field_data)
        
        discord_payload.append(type_payload)
    
    # Send data to Discord webhook
    if discord_payload:
        payload = {'embeds': discord_payload}
        push_to_discord(payload)

if __name__ == "__main__":
    main()