import asyncio
import rlapi

async def main():
    client = rlapi.Client()
    
    # Replace with actual platform|id (e.g. "Steam|123456789")
    player = await client.find_player("Steam|76561198000000000")
    
    print(f"Player: {player.name}")
    print(f"Platform: {player.platform}")
    print(f"Ranked 2v2: {player.ranks.twos}")
    print(f"Ranked 3v3: {player.ranks.threes}")

asyncio.run(main())
