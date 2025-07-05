import discord
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")

intents = discord.Intents.all()  # FULL intents to eliminate doubt
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'✅ Logged in as {client.user.name}')

@client.event
async def on_message(message):
    print(f"📨 Received: {message.content} from {message.author}")
    if message.author == client.user:
        return
    if message.content.startswith("!test"):
        await message.channel.send("✅ I heard you!")

client.run(TOKEN)
