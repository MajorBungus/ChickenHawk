import discord
import aiohttp
import asyncio
import datetime
from rlapi import Client as RLClient
from collections import defaultdict
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
PUBG_API_KEY = os.getenv('PUBG_API_KEY')

# Set up Discord client with intents
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# Cache for player name to account ID
account_id_cache = {}

# Rocket League API client
rl_client = RLClient()

# PUBG API headers
HEADERS = {
    'Authorization': f'Bearer {PUBG_API_KEY}',
    'Accept': 'application/vnd.api+json'
}

# PUBG map name mapping
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

    content = message.content

    if content.startswith(('!pubgstats', '!pubglog', '!pubgsummary')):
        parts = content.split()
        if len(parts) < 2:
            await send_usage_instructions(message.channel)
            return

        player_name = parts[1]
        print(f"Author: {message.author} | Content: '{content}'")

        if content.startswith('!pubgstats'):
            await message.channel.send(f"Fetching all PUBG stats for {player_name}... please wait ⏳")
            await send_stats_embed(player_name, message)
            await send_season_embed(player_name, message)
            await send_lifetime_embed(player_name, message)

        elif content.startswith('!pubglog'):
            await message.channel.send(f"Fetching last 10 matches for {player_name}... please wait ⏳")
            await send_log_embed(player_name, message)

        elif content.startswith('!pubgsummary'):
            await message.channel.send(f"Fetching full PUBG summary for {player_name}... please wait ⏳")
            await send_stats_embed(player_name, message)
            await send_log_embed(player_name, message)
            await send_season_embed(player_name, message)
            await send_lifetime_embed(player_name, message)

    elif content.startswith('!rllog'):
        await handle_rl_log(message)

    elif content.startswith('!rlstats'):
        parts = content.split()
        if len(parts) < 2:
            await message.channel.send("Usage: `!rlstats <PlayerName>`")
            return

        player_name = parts[1]
        await message.channel.send(f"Fetching Rocket League stats for {player_name}... please wait 🏎️")
        await send_rlstats_embeds(player_name, message.channel)


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
                if 'data' not in data or not data['data']:
                    raise Exception(f"No data found for {player_name}.")
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

# Full implementations from `pubg_bot (3).py` including:
# - fetch_match_data
# - send_stats_embed
# - send_season_embed
# - send_lifetime_embed
# - send_log_embed
# - send_usage_instructions
# - send_rlstats_embeds
# - handle_rl_log

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

async def send_lifetime_embed(player_name, message):
    try:
        async with aiohttp.ClientSession() as session:
            if player_name not in account_id_cache:
                async with session.get(f'https://api.pubg.com/shards/steam/players?filter[playerNames]={player_name}', headers=HEADERS) as resp:
                    data = await resp.json()
                if 'data' not in data or not data['data']:
                    raise Exception(f"No data found for {player_name}.")
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
            match_link = f"
🔗 [View Match Details](https://pubglookup.com/players/steam/{player_name}/matches/{m['match_id']})"

            value_str = (
                f"Time Alive: {m['time_alive']}m
"
                f"Kills: {m['kills']} | Deaths: {m['deaths']} | Damage: {m['damage']} | **K/D: {kd}**
"
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
    embed.add_field(name="!rlstats <PlayerName>", value="→ Rocket League Win % (Season + Lifetime)", inline=False)

    await channel.send(embed=embed)


async def send_rlstats_embeds(player_name, channel):
    try:
        player = await rl_client.find_player(player_name)
        stats = player.stats

        current = stats.season
        lifetime = stats.lifetime

        current_win_pct = (current.wins / current.games_played * 100) if current.games_played else 0
        lifetime_win_pct = (lifetime.wins / lifetime.games_played * 100) if lifetime.games_played else 0

        cur_avg_goals = current.goals / current.games_played if current.games_played else 0
        cur_avg_assists = current.assists / current.games_played if current.games_played else 0
        cur_avg_saves = current.saves / current.games_played if current.games_played else 0
        cur_avg_demos = current.demos / current.games_played if current.games_played else 0

        life_avg_goals = lifetime.goals / lifetime.games_played if lifetime.games_played else 0
        life_avg_assists = lifetime.assists / lifetime.games_played if lifetime.games_played else 0
        life_avg_saves = lifetime.saves / lifetime.games_played if lifetime.games_played else 0
        life_avg_demos = lifetime.demos / lifetime.games_played if lifetime.games_played else 0

        embed_current = discord.Embed(
        title=f"{player_name} — Rocket League (Current Season)",
        color=0x7a5cff
    )
    embed_current.add_field(name="Rank", value=str(current.rank or "Unknown"), inline=True)
        embed_current.add_field(name="Games Played", value=str(current.games_played), inline=True)
        embed_current.add_field(name="Wins", value=str(current.wins), inline=True)
        embed_current.add_field(name="Win %", value=f"{current_win_pct:.1f}%", inline=True)
        embed_current.add_field(name="Avg Goals", value=f"{cur_avg_goals:.2f}", inline=True)
        embed_current.add_field(name="Avg Assists", value=f"{cur_avg_assists:.2f}", inline=True)
        embed_current.add_field(name="Avg Saves", value=f"{cur_avg_saves:.2f}", inline=True)
        embed_current.add_field(name="Avg Demos", value=f"{cur_avg_demos:.2f}", inline=True)

        embed_lifetime = discord.Embed(
        title=f"{player_name} — Rocket League (Lifetime)",
        color=0x9e7dff
    )
    embed_lifetime.add_field(name="Rank", value=str(lifetime.rank or "Unknown"), inline=True)
        embed_lifetime.add_field(name="Games Played", value=str(lifetime.games_played), inline=True)
        embed_lifetime.add_field(name="Wins", value=str(lifetime.wins), inline=True)
        embed_lifetime.add_field(name="Win %", value=f"{lifetime_win_pct:.1f}%", inline=True)
        embed_lifetime.add_field(name="Avg Goals", value=f"{life_avg_goals:.2f}", inline=True)
        embed_lifetime.add_field(name="Avg Assists", value=f"{life_avg_assists:.2f}", inline=True)
        embed_lifetime.add_field(name="Avg Saves", value=f"{life_avg_saves:.2f}", inline=True)
        embed_lifetime.add_field(name="Avg Demos", value=f"{life_avg_demos:.2f}", inline=True)

        await channel.send(embed=embed_current)
        await channel.send(embed=embed_lifetime)
        print(f"[SUCCESS] Sent Rocket League detailed stats for {player_name}")
    except Exception as e:
        await channel.send(f"⚠️ Error fetching Rocket League stats: {e}")
        print(f"[ERROR] Rocket League stats fetch failed: {e}")


async def handle_rl_log(message):
    await message.channel.typing()
    try:
        player_name = message.content.split(' ', 1)[1]
        player = await rl_client.find_player(player_name)
        match_history = await player.get_match_history(limit=10)

        if not match_history:
            await message.channel.send("No Rocket League match history found for this player.")
            return

        description = ""
        for i, match in enumerate(match_history, 1):
            result = "✅ Win" if match.get('won') else "❌ Loss"
            rank = match.get('rank', 'Unranked')
            goals = match.get('goals', 0)
            assists = match.get('assists', 0)
            saves = match.get('saves', 0)
            demos = match.get('demos', 0)

            description += (
                f"**Match {i} – {result}**
"
                f"Rank: `{rank}`
"
                f"Goals: `{goals}` | Assists: `{assists}` | Saves: `{saves}` | Demos: `{demos}`

"
            )

        embed = discord.Embed(
            title=f"Rocket League Match Log: {player_name}",
            description=description.strip(),
            color=discord.Color.orange()
        )
        await message.channel.send(embed=embed)

    except Exception as e:
        await message.channel.send(f"⚠️ Error fetching Rocket League match log: {e}")


# FINAL EXECUTION
if __name__ == '__main__':
    print("Starting ChickenHawk bot...")
    client.run(DISCORD_BOT_TOKEN)
