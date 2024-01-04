import requests
import json
import os
# from datetime import datetime, timedelta


def push_to_discord(webhook, payload):
    headers = {'Content-Type': 'application/json'}
    try:
        response = requests.post(
            webhook, data=json.dumps(payload), headers=headers)
        response.raise_for_status()
        response.cookies
        print("Data sent to Discord successfully.")
    except requests.exceptions.RequestException as e:
        print(f"Error sending to Discord: {e}")
        print(payload)


def get_sanitized_string(input_string):
    replace_values = {
        'ß': 'ss', 'à': 'a', 'á': 'a', 'â': 'a', 'ã': 'a', 'ä': 'a', 'å': 'a',
        'æ': 'ae', 'ç': 'c', 'è': 'e', 'é': 'e', 'ê': 'e', 'ë': 'e', 'ì': 'i',
        'í': 'i', 'î': 'i', 'ï': 'i', 'ð': 'd', 'ñ': 'n', 'ò': 'o', 'ó': 'o',
        'ô': 'o', 'õ': 'o', 'ö': 'o', 'ø': 'o', 'ù': 'u', 'ú': 'u', 'û': 'u',
        'ü': 'u', 'ý': 'y', 'þ': 'p', 'ÿ': 'y', '“': '"', '”': '"', '·': '-',
        ':': ''
    }

    for key, value in replace_values.items():
        input_string = input_string.replace(key, value)

    return input_string


# Load config from file
script_directory = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(script_directory, 'config.json')
# config_path = 'D:\\GitHub\\Tautulli2Discord-python\\config.json'

with open(config_path, 'r') as config_file:
    config = json.load(config_file)

# Script name from config
script_name = 'TopUsersByMediaType'

# Assign variables from config
discord_webhook = config['ScriptSettings'][script_name]['Webhook']
media_types = config['ScriptSettings'][script_name]['MediaTypes']
count = config['ScriptSettings'][script_name]['Count']
days = config['ScriptSettings'][script_name]['Days']
tautulli_url = config['Tautulli']['Url']
tautulli_api_key = config['Tautulli']['APIKey']

# SQL query
query = f"""
SELECT
COALESCE(
   MAX(
      CASE
         WHEN friendly_name IS NOT NULL AND TRIM(friendly_name) <> '' THEN friendly_name
      END
   ),
   MAX(
      CASE
         WHEN username IS NOT NULL AND TRIM(username) <> '' THEN username
         ELSE 'Unknown'
      END
   )
) AS FriendlyName,
CASE
   WHEN media_type = 'episode' THEN 'TV'
   WHEN media_type = 'movie' THEN 'Movies'
   WHEN media_type = 'track' THEN 'Music'
   ELSE media_type
END AS MediaType,
count(user) AS Plays
FROM (
   SELECT
   session_history.user,
   session_history.user_id,
   users.username,
   users.friendly_name,
   started,
   session_history_metadata.media_type
   FROM session_history
   JOIN session_history_metadata
      ON session_history_metadata.id = session_history.id
   LEFT OUTER JOIN users
      ON session_history.user_id = users.user_id
   WHERE datetime(session_history.stopped, 'unixepoch', 'localtime') >= datetime('now', '-{days} days', 'localtime')
   AND users.user_id <> 0
   GROUP BY session_history.reference_id
) AS Results
GROUP BY user, media_type
"""

# Execute Tautulli query
tautulli_query_results = requests.get(
    f"{tautulli_url}/api/v2?apikey={tautulli_api_key}&cmd=sql&query={query}").json()
top_users_by_media_type = {}

# print(json.dumps(tautulli_query_results['response']['data'], indent=2))

# Organize data by MediaType
for entry in tautulli_query_results['response']['data']:
    media_type = entry['MediaType']
    if media_type not in top_users_by_media_type:
        top_users_by_media_type[media_type] = []
    top_users_by_media_type[media_type].append(entry)

# print(json.dumps(top_users_by_media_type['TV'], indent=2))

# Process and send results to Discord
for media_type, plays in top_users_by_media_type.items():
    sorted_users = sorted(
        plays, key=lambda x: x['Plays'], reverse=True)[:count]
    max_friendly_name_length = max(
        len(user['FriendlyName']) for user in sorted_users)
    template = '{:<{}}\t{}'
    str_body = '\n'.join([template.format(user['FriendlyName'], max_friendly_name_length,
                                          user['Plays']) for user in sorted_users])
    payload = {
        'content': f"**Top {count} users in {media_type}** for the last **{days}** Days!\n```\n{str_body}\n```"
    }

    push_to_discord(discord_webhook, payload)
