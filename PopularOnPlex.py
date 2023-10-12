import requests
import json
import unicodedata
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
    def get_tmdb_info(tmdb_api_key, tautulli_url, tautulli_api_key, media_type, title=None, year=None, rating_key=None):
        tmdb_id = None
        
        # Try to get TMDB ID from Tautulli if rating_key is provided
        if rating_key:
            tautulli_params = {
                "apikey": tautulli_api_key,
                "cmd": "get_metadata",
                "rating_key": rating_key
            }
            
            tautulli_response = requests.get(f"{tautulli_url}/api/v2", params=tautulli_params)
            
            if tautulli_response.status_code == 200:
                tautulli_data = tautulli_response.json()
                if tautulli_data["response"]["data"]:
                    # Look for the TMDB GUID in the list of GUIDs
                    tmdb_guid = next((guid for guid in tautulli_data["response"]["data"]["guids"] if guid.startswith("tmdb://")), None)
                    if tmdb_guid:
                        # Extract the TMDB ID from the TMDB GUID
                        tmdb_id = tmdb_guid.split("tmdb://")[1]
        
        # If TMDB ID found in Tautulli, use it to lookup the media information
        if tmdb_id:
            media_url = f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}?api_key={tmdb_api_key}&language=en-US"
            media_results = requests.get(media_url).json()
            if "success" in media_results and media_results["success"] is False:
                # If TMDB ID lookup returns no data, return None
                return None
            return media_results
        # No TMDB ID, so will will attempt to search TMDB for the media information
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
    
    # Parse the config file and assign variables
    config = load_config()
    script_name = 'PopularOnPlex'
    script_settings = config['ScriptSettings'][script_name]
    discord_webhook = script_settings['Webhook']
    count = script_settings['Count']
    days = script_settings['Days']
    tautulli_url = config['Tautulli']['Url']
    tautulli_api_key = config['Tautulli']['APIKey']
    tmdb_api_key = config['TMDB']['APIKey']
    
    response = requests.get(f"{tautulli_url}/api/v2", params={"apikey": tautulli_api_key, "cmd": "get_server_info"})
    plex_server_identifier = response.json()["response"]["data"]["pms_identifier"]
    
    response = requests.get(f"{tautulli_url}/api/v2", params={"apikey": tautulli_api_key, "cmd": "get_home_stats", "grouping": 1, "time_range": days, "stats_count": count})
    data = response.json()["response"]["data"]
    
    # Find the sections for "popular_movies" and "popular_tv"
    sections = {}
    for item in data:
        sections[item["stat_id"]] = item["rows"]
    
    # Get the lists for "popular_movies" and "popular_tv" or set to empty lists if not found
    top_movies = sections.get("popular_movies", [])
    top_tv_shows = sections.get("popular_tv", [])
    
    top_movies_embed = []
    top_tv_shows_embed = []
    
    for movie in top_movies:
        sanitized_title = get_sanitized_string(movie["title"])
        tmdb_movie_results = get_tmdb_info(tmdb_api_key, tautulli_url, tautulli_api_key, media_type="movie", title=sanitized_title, year=movie["year"], rating_key=movie["rating_key"])
        
        if tmdb_movie_results:
            movie_embed_params = {
                "color": 13400320,
                "title": sanitized_title,
                "url": f"https://www.themoviedb.org/movie/{tmdb_movie_results['id']}",
                "author": {
                    "name": "Open on Plex",
                    "url": f"https://app.plex.tv/desktop/#!/server/{plex_server_identifier}/details?key=%2Flibrary%2Fmetadata%2F{movie['rating_key']}",
                    "icon_url": "https://i.imgur.com/FNoiYXP.png"
                },
                "description": get_sanitized_string(tmdb_movie_results["overview"]),
                "thumbnail": {"url": f"https://image.tmdb.org/t/p/w500{tmdb_movie_results['poster_path']}"},
                "fields": [
                    {"name": "Rating", "value": f"{tmdb_movie_results['vote_average']} :star:'s", "inline": False},
                    {"name": "Users Watched", "value": movie["users_watched"], "inline": True},
                    {"name": "Released", "value": movie["year"], "inline": True}
                ],
                "footer": {"text": "Updated"},
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            movie_embed_params = {
                "color": 13400320,
                "title": sanitized_title,
                "url": "https://www.themoviedb.org/movie/",
                "author": {
                    "name": "Open on Plex",
                    "url": f"https://app.plex.tv/desktop/#!/server/{plex_server_identifier}/details?key=%2Flibrary%2Fmetadata%2F{movie['rating_key']}",
                    "icon_url": "https://i.imgur.com/FNoiYXP.png"
                },
                "description": "Unknown",
                "thumbnail": {"url": "https://www.programmableweb.com/sites/default/files/TMDb.jpg"},
                "fields": [
                    {"name": "Rating", "value": "??? :star:'s", "inline": False},
                    {"name": "Users Watched", "value": movie["users_watched"], "inline": True},
                    {"name": "Released", "value": movie["year"], "inline": True}
                ],
                "footer": {"text": "Updated"},
                "timestamp": datetime.utcnow().isoformat()
            }
        
        top_movies_embed.append(movie_embed_params)
    
    for show in top_tv_shows:
        sanitized_title = get_sanitized_string(show["title"])
        tmdb_tv_results = get_tmdb_info(tmdb_api_key, tautulli_url, tautulli_api_key, "tv", sanitized_title, show["year"], show["rating_key"])
        
        if tmdb_tv_results:
            # Check for the existence of 'episode_run_time'
            if "episode_run_time" in tmdb_tv_results and tmdb_tv_results["episode_run_time"]:
                runtime = f"{tmdb_tv_results['episode_run_time'][0]} Minutes"
            else:
                runtime = "Unknown"
                
            tv_show_embed_params = {
                "color": 40635,
                "title": sanitized_title,
                "url": f"https://www.themoviedb.org/tv/{tmdb_tv_results['id']}",
                "author": {
                    "name": "Open on Plex",
                    "url": f"https://app.plex.tv/desktop/#!/server/{plex_server_identifier}/details?key=%2Flibrary%2Fmetadata%2F{show['rating_key']}",
                    "icon_url": "https://i.imgur.com/FNoiYXP.png"
                },
                "description": get_sanitized_string(tmdb_tv_results["overview"]),
                "thumbnail": {"url": f"https://image.tmdb.org/t/p/w500{tmdb_tv_results['poster_path']}"},
                "fields": [
                    {"name": "Rating", "value": f"{tmdb_tv_results['vote_average']} :star:'s", "inline": False},
                    {"name": "Users Watched", "value": show["users_watched"], "inline": True},
                    {"name": "Seasons", "value": f"{tmdb_tv_results['number_of_seasons']} Seasons", "inline": True},
                    {"name": "Runtime", "value": runtime, "inline": True}
                ],
                "footer": {"text": "Updated"},
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            tv_show_embed_params = {
                "color": 40635,
                "title": sanitized_title,
                "author": {
                    "name": "Open on Plex",
                    "url": f"https://app.plex.tv/desktop/#!/server/{plex_server_identifier}/details?key=%2Flibrary%2Fmetadata%2F{show['rating_key']}",
                    "icon_url": "https://i.imgur.com/FNoiYXP.png"
                },
                "description": "Unknown",
                "fields": [
                    {"name": "Rating", "value": "??? :star:'s", "inline": False},
                    {"name": "Users Watched", "value": show["users_watched"], "inline": True},
                    {"name": "Seasons", "value": "??? Seasons", "inline": True},
                    {"name": "Runtime", "value": "??? Minutes", "inline": True}
                ],
                "footer": {"text": "Updated"},
                "timestamp": datetime.utcnow().isoformat()
            }
        
        top_tv_shows_embed.append(tv_show_embed_params)
    
    movies_payload = {
        "username": "Popular on Plex",
        "content": "**Popular Movies on Plex:**",
        "embeds": top_movies_embed
    }
    
    push_to_discord(discord_webhook, movies_payload)
    
    shows_payload = {
        "username": "Popular on Plex",
        "content": "**Popular TV Shows on Plex:**",
        "embeds": top_tv_shows_embed
    }
    
    push_to_discord(discord_webhook, shows_payload)

# Call the main function
if __name__ == "__main__":
    main()