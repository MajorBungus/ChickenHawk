import discord
import aiohttp
import asyncio
import datetime
from collections import defaultdict

import os
import requests  # ✅ New import for metadata fallback

def get_env_or_metadata(key):
    value = os.getenv(key)
    if not value:
        try:
            res = requests.get(
                f'http://metadata.google.internal/computeMetadata/v1/instance/attributes/{key}',
                headers={'Metadata-Flavor': 'Google'}
            )
            if res.status_code == 200:
                return res.text
        except Exception as e:
            print(f"⚠️ Could not retrieve {key} from metadata: {e}")
    return value

DISCORD_BOT_TOKEN = get_env_or_metadata('DISCORD_BOT_TOKEN')
PUBG_API_KEY = get_env_or_metadata('PUBG_API_KEY')



intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# Cache for player name to account ID
account_id_cache = {}

HEADERS = {
    'Authorization': f'Bearer {PUBG_API_KEY}',
    'Accept': 'application/vnd.api+json'
}

map_name_mapping = {
    "Baltic_Main": ("Erangel", "🌲"),
    "Desert_Main": ("Miramar", "🌵"),
    "DihorOtok_Main": ("Vikendi", "❄️"),
    "Savage_Main": ("Sanhok", "🏝️"),
    "Chimera_Main": ("Paramo", "🌋"),
    "Tiger_Main": ("Taego", "🐟"),
    "Kiki_Main": ("Deston", "🏢"),
    "Neon_Main": ("Rondo", "⛩️")
}

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith('!pubgstats') or message.content.startswith('!pubglog') or message.content.startswith('!pubgsummary'):
        parts = message.content.split()
        if len(parts) < 2:
            await send_usage_instructions(message.channel)
            return

        player_name = parts[1]
        print(f"Author: {message.author} | Content: '{message.content}'")

        if message.content.startswith('!pubgstats'):
            await message.channel.send(f"Fetching all PUBG stats for {player_name}... please wait ⏳")
            await send_stats_embed(player_name, message)
            await send_season_embed(player_name, message)
            await send_lifetime_embed(player_name, message)
        elif message.content.startswith('!pubglog'):
            await message.channel.send(f"Fetching last 10 matches for {player_name}... please wait ⏳")
            await send_log_embed(player_name, message)
        elif message.content.startswith('!pubgsummary'):
            await message.channel.send(f"Fetching full PUBG summary for {player_name}... please wait ⏳")
            await send_stats_embed(player_name, message)
            await send_log_embed(player_name, message)
            await send_season_embed(player_name, message)
            await send_lifetime_embed(player_name, message)

async def fetch_match_data(player_name):
    async with aiohttp.ClientSession() as session:
        if player_name not in account_id_cache:
            async with session.get(f'https://api.pubg.com/shards/steam/players?filter[playerNames]={player_name}', headers=HEADERS) as resp:
                if resp.status != 200:
                    raise Exception(f"Could not fetch player ID for {player_name} (status: {resp.status})")
                data = await resp.json()
                if not data['data']:
                    raise Exception(f"No data found for {player_name}.")
                account_id = data['data'][0]['id']
                account_id_cache[player_name] = account_id
        else:
            account_id = account_id_cache[player_name]

        async with session.get(f'https://api.pubg.com/shards/steam/players/{account_id}', headers=HEADERS) as resp:
            data = await resp.json()
            match_ids = [match['id'] for match in data['data']['relationships']['matches']['data'][:10]]

        matches = []
        for match_id in match_ids:
            async with session.get(f'https://api.pubg.com/shards/steam/matches/{match_id}', headers=HEADERS) as resp:
                match_data = await resp.json()
                participants = [x for x in match_data['included'] if x['type'] == 'participant']
                rosters = [x for x in match_data['included'] if x['type'] == 'roster']
                participant = next((x for x in participants if x['attributes']['stats']['name'].lower() == player_name.lower()), None)
                if not participant:
                    continue
                stats = participant['attributes']['stats']
                participant_id = participant['id']
                teammates = []
                placement = None
                for roster in rosters:
                    participant_ids = [p['id'] for p in roster['relationships']['participants']['data']]
                    if participant_id in participant_ids:
                        teammates = [x['attributes']['stats']['name'] for x in participants if x['id'] in participant_ids and x['id'] != participant_id]
                        placement = roster['attributes']['stats']['rank']
                        break

                map_raw = match_data['data']['attributes']['mapName']
                map_pretty, map_emoji = map_name_mapping.get(map_raw, (map_raw, ""))

                matches.append({
                    'match_id': match_id,
                    'placement': placement,
                    'map': map_pretty,
                    'map_emoji': map_emoji,
                    'time_alive': stats['timeSurvived'] // 60,
                    'kills': stats['kills'],
                    'deaths': 1 if stats['deathType'] != 'alive' else 0,
                    'damage': round(stats['damageDealt']),
                    'teammates': teammates
                })

        return matches

async def send_stats_embed(player_name, message):
    try:
        matches = await fetch_match_data(player_name)

        total_kills = sum(m['kills'] for m in matches)
        total_deaths = sum(m['deaths'] for m in matches)
        kd_ratio = round(total_kills / total_deaths, 2) if total_deaths > 0 else total_kills
        most_kills = max(m['kills'] for m in matches)

        embed = discord.Embed(title=f"{player_name} — Last 10 Matches (Summary)", color=0xFFD700)
        embed.add_field(name="K/D", value=str(kd_ratio), inline=False)
        embed.add_field(name="Most Kills", value=str(most_kills), inline=False)
        embed.add_field(name="Total Kills", value=str(total_kills), inline=False)
        embed.add_field(name="Total Deaths", value=str(total_deaths), inline=False)
        await message.channel.send(embed=embed)
        print(f"[SUCCESS] Sent high-level summary for {player_name}")
    except Exception as e:
        error_msg = str(e)
        if "No data found" in error_msg or "Could not fetch player ID" in error_msg:
            await message.channel.send(f"❌ No data found for player **{player_name}**. Make sure the name is correct.")
        else:
            await message.channel.send(f"⚠️ Error: {e}")

async def send_season_embed(player_name, message):
    try:
        async with aiohttp.ClientSession() as session:
            if player_name not in account_id_cache:
                async with session.get(f'https://api.pubg.com/shards/steam/players?filter[playerNames]={player_name}', headers=HEADERS) as resp:
                    data = await resp.json()
                    account_id = data['data'][0]['id']
                    account_id_cache[player_name] = account_id
            else:
                account_id = account_id_cache[player_name]

            async with session.get('https://api.pubg.com/shards/steam/seasons', headers=HEADERS) as resp:
                season_data = await resp.json()
                current_season = next((s['id'] for s in season_data['data'] if s['attributes']['isCurrentSeason']), None)

            async with session.get(f'https://api.pubg.com/shards/steam/players/{account_id}/seasons/{current_season}', headers=HEADERS) as resp:
                data = await resp.json()
                stats = data['data']['attributes']['gameModeStats'].get('squad-fpp') or {}
                games = stats.get('roundsPlayed', 0)
                kills = stats.get('kills', 0)
                deaths = stats.get('losses', 0)
                kd = round(kills / deaths, 2) if deaths > 0 else kills

            embed = discord.Embed(title=f"{player_name} — Current Season", color=0x3399FF)
            embed.add_field(name="Games Played", value=str(games), inline=False)
            embed.add_field(name="K/D", value=str(kd), inline=False)
            await message.channel.send(embed=embed)
            print(f"[SUCCESS] Sent season stats for {player_name}")
    except Exception as e:
        error_msg = str(e)
        if "No data found" in error_msg or "Could not fetch player ID" in error_msg:
            await message.channel.send(f"❌ No data found for player **{player_name}**. Make sure the name is correct.")
        else:
            await message.channel.send(f"⚠️ Error: {e}")

async def send_lifetime_embed(player_name, message):
    try:
        async with aiohttp.ClientSession() as session:
            if player_name not in account_id_cache:
                async with session.get(f'https://api.pubg.com/shards/steam/players?filter[playerNames]={player_name}', headers=HEADERS) as resp:
                    data = await resp.json()
                    account_id = data['data'][0]['id']
                    account_id_cache[player_name] = account_id
            else:
                account_id = account_id_cache[player_name]

            async with session.get(f'https://api.pubg.com/shards/steam/players/{account_id}/seasons/lifetime', headers=HEADERS) as resp:
                data = await resp.json()
                stats = data['data']['attributes']['gameModeStats'].get('squad-fpp') or {}
                games = stats.get('roundsPlayed', 0)
                kills = stats.get('kills', 0)
                deaths = stats.get('losses', 0)
                kd = round(kills / deaths, 2) if deaths > 0 else kills

            embed = discord.Embed(title=f"{player_name} — Lifetime Stats", color=0x800080)
            embed.add_field(name="Games Played", value=str(games), inline=False)
            embed.add_field(name="K/D", value=str(kd), inline=False)
            await message.channel.send(embed=embed)
            print(f"[SUCCESS] Sent lifetime stats for {player_name}")
    except Exception as e:
        error_msg = str(e)
        if "No data found" in error_msg or "Could not fetch player ID" in error_msg:
            await message.channel.send(f"❌ No data found for player **{player_name}**. Make sure the name is correct.")
        else:
            await message.channel.send(f"⚠️ Error: {e}")

async def send_log_embed(player_name, message):
    try:
        matches = await fetch_match_data(player_name)

        embed = discord.Embed(title=f"{player_name} — Last 10 Matches (Log)", color=0xFFFFFF)

        for i, m in enumerate(matches, 1):
            placement_str = f"**{m['placement']}**" if m['placement'] == 1 else str(m['placement'])
            match_line = f"{'🏆 ' if m['placement'] == 1 else ''}MATCH **{i}** - {m['map_emoji']} {m['map']} - Placement: {placement_str}"

            kd = round(m['kills'] / m['deaths'], 2) if m['deaths'] > 0 else m['kills']
            teammates_str = ', '.join(m['teammates']) if m['teammates'] else 'None'
            match_link = f"\n🔗 [View Match Details](https://pubglookup.com/players/steam/{player_name}/matches/{m['match_id']})"

            value_str = (
                f"Time Alive: {m['time_alive']}m\n"
                f"Kills: {m['kills']} | Deaths: {m['deaths']} | Damage: {m['damage']} | **K/D: {kd}**\n"
                f"Teammates: {teammates_str}"
                f"{match_link}"
            )

            embed.add_field(
                name=match_line,
                value=value_str,
                inline=False
            )

        await message.channel.send(embed=embed)
        print(f"[SUCCESS] Sent match log for {player_name}")
    except Exception as e:
        error_msg = str(e)
        if "No data found" in error_msg or "Could not fetch player ID" in error_msg:
            await message.channel.send(f"❌ No data found for player **{player_name}**. Make sure the name is correct.")
        else:
            await message.channel.send(f"⚠️ Error: {e}")
        
async def send_usage_instructions(channel):
    embed = discord.Embed(
        title="🐔 ChickenHawk Command Usage",
        description="Use the following commands with a valid PUBG player name (replace <PlayerName> entirely):",
        color=0x3498DB
    )
    embed.add_field(name="!pubgstats <PlayerName>", value="→ Shows stats for last 10 matches, season, and lifetime", inline=False)
    embed.add_field(name="!pubglog <PlayerName>", value="→ Shows detailed log for last 10 matches", inline=False)
    embed.add_field(name="!pubgsummary <PlayerName>", value="→ Shows stats + log", inline=False)
    await channel.send(embed=embed)
    
if __name__ == '__main__':
    print("Starting PUBG bot...")
    client.run(DISCORD_BOT_TOKEN)
