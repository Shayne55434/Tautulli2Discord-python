import re
import requests
import json
import os

# Get the directory where the script is located
script_directory = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(script_directory, 'config.json')
# config_path = 'D:\\GitHub\\Tautulli2Discord-python\\config.json'


def load_config():
    with open(config_path, 'r') as config_file:
        return json.load(config_file)


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
        print(f"Response content: {response.content}")
        print(payload)


def get_sanitized_string(str_input_string):
    # Credit to FS.Corrupt for the initial version of this function. https://github.com/FSCorrupt
    # This will match any titles with the year appended. I ran into issues with 'Yellowstone (2018)'
    reg_appended_year = re.compile(r' \(([0-9]{4})\)')

    replace_values = {
        'ß': 'ss',
        'à': 'a',
        'á': 'a',
        'â': 'a',
        'ã': 'a',
        'ä': 'a',
        'å': 'a',
        'æ': 'ae',
        'ç': 'c',
        'è': 'e',
        'é': 'e',
        'ê': 'e',
        'ë': 'e',
        'ì': 'i',
        'í': 'i',
        'î': 'i',
        'ï': 'i',
        'ð': 'd',
        'ñ': 'n',
        'ò': 'o',
        'ó': 'o',
        'ô': 'o',
        'õ': 'o',
        'ö': 'o',
        'ø': 'o',
        'ù': 'u',
        'ú': 'u',
        'û': 'u',
        'ü': 'u',
        'ý': 'y',
        'þ': 'p',
        'ÿ': 'y',
        '“': '"',
        '”': '"',
        '·': '-',
        ':': '',
    }

    str_input_string = reg_appended_year.sub('', str_input_string)

    translation_table = str.maketrans(replace_values)
    str_input_string = str_input_string.translate(translation_table)

    return str_input_string


def main():
    config = load_config()
    script_name = 'TopPlexStats'
    script_settings = config['ScriptSettings'][script_name]
    discord_webhook = script_settings['Webhook']
    count = script_settings['Count']
    days = script_settings['Days']
    tautulli_url = config['Tautulli']['Url']
    tautulli_api_key = config['Tautulli']['APIKey']

    # Get Home Stats from Tautulli
    tautulli_home_stats_url = f"{tautulli_url}/api/v2?apikey={
        tautulli_api_key}&cmd=get_home_stats&grouping=1&time_range={days}&stats_count={count}"
    response = requests.get(tautulli_home_stats_url).json()
    tautulli_home_stats = response['response']['data']
    all_stats_object = []

    for stat in tautulli_home_stats:
        stat_id = stat['stat_id']
        rows = stat['rows']

        if stat_id == 'top_users':
            top_users = sorted(rows, key=lambda x: x.get(
                'total_plays', 0), reverse=True)[:count]
            group_stats = []
            for user in top_users:
                current_stats = {
                    'Metric': user.get('friendly_name', ''),
                    'Value': f"{user.get('total_plays', 0)} plays"
                }
                group_stats.append(current_stats)
            all_stats_object.append({
                'Group': f'Top {count} Users Overall',
                'Stats': group_stats
            })

        elif stat_id == 'top_platforms':
            top_platforms = sorted(rows, key=lambda x: x.get(
                'total_plays', 0), reverse=True)[:count]
            group_stats = []
            for platform in top_platforms:
                current_stats = {
                    'Metric': platform.get('platform', ''),
                    'Value': f"{platform.get('total_plays', 0)} plays"
                }
                group_stats.append(current_stats)
            all_stats_object.append({
                'Group': f'Top {count} Platforms',
                'Stats': group_stats
            })

        elif stat_id == 'most_concurrent':
            most_concurrent = sorted(
                rows, key=lambda x: x.get('count', 0), reverse=True)
            group_stats = []
            for stat in most_concurrent:
                current_stats = {
                    'Metric': stat.get('title', ''),
                    'Value': stat.get('count', 0)
                }
                group_stats.append(current_stats)
            all_stats_object.append({
                'Group': 'Top Concurrent Streams',
                'Stats': group_stats
            })

    # print(json.dumps(all_stats_object, indent=2))

    # Convert results to string and send to Discord
    for group_entry in all_stats_object:
        group_name = group_entry['Group']
        group_stats = group_entry['Stats']
        max_metric_length = max(len(stat['Metric']) for stat in group_stats)
        template = '{:<{}}\t{}'
        str_body = '\n'.join([template.format(stat['Metric'], max_metric_length,
                                              stat['Value']) for stat in group_stats])
        payload = {
            'content': f"**{group_name}** for the last **{days}** Days!\n```\n{str_body}\n```"
        }
        push_to_discord(discord_webhook, payload)


if __name__ == "__main__":
    main()
