import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
import requests
import anthropic

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    print("------")

@bot.command()
async def ping(ctx):
    await ctx.send("Pong! JARVIS is online.")

@bot.command()
async def run(ctx, avenger: str):
    avenger = avenger.upper()
    await ctx.send(f"Roger that, sir. Booting up {avenger}...")
    
    if avenger == "CAP":
        try:
            headers = {"x-api-key": "jarvis-secret-key-2026"}
            res = requests.post("http://localhost:3456/generate", json={"topic": "Daily Short", "type": "short"}, headers=headers)
            await ctx.send(f"CAP responded: {res.text[:200]}")
        except Exception as e:
            await ctx.send(f"Error connecting to CAP: {e}")
            
    elif avenger == "FACTORY":
        try:
            import subprocess
            subprocess.Popen(["/opt/agency/Jarvis-Agency-Office/.venv/bin/python", "/opt/agency/Jarvis-Agency-Office/jarvis_video_factory.py"])
            await ctx.send("🚀 Telugu Video Factory started in the background.")
        except Exception as e:
            await ctx.send(f"Error starting factory: {e}")
    else:
        await ctx.send(f"{avenger} is not active yet.")

@bot.command()
async def fix(ctx, filename: str, *args):
    error_description = " ".join(args)
    await ctx.send(f"🔧 Analyzing {filename} to fix: {error_description}...")
    
    filepath = f"/opt/agency/Jarvis-Agency-Office/{filename}"
    if not os.path.exists(filepath):
        await ctx.send(f"❌ File not found: {filename}")
        return

    with open(filepath, "r") as f:
        current_code = f.read()

    manual_path = "/opt/agency/Jarvis-Agency-Office/agency_manual.md"
    manual = ""
    if os.path.exists(manual_path):
        with open(manual_path, "r") as f:
            manual = f.read()

    client = anthropic.Anthropic(
        base_url="http://127.0.0.1:8082", 
        api_key="freecc"
    )
    
    prompt = f"""You are JARVIS, the CTO of the AI Agency. 
Here is the Architect's Manual (The rules of the agency):
{manual}

Error: {error_description}

Here is the current code:
{current_code}

Please rewrite the ENTIRE file, fixing the error based on the Architect's Manual. 
Return ONLY the raw Python code, no markdown, no explanations."""
    
    try:
        response = client.messages.create(
            model="nvidia_nim/nvidia/nemotron-3-ultra-550b-a55b",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Extract text ignoring thinking blocks
        fixed_code = "".join([block.text for block in response.content if hasattr(block, 'text')]).strip()
        
        if fixed_code.startswith("```"):
            fixed_code = "\n".join(fixed_code.split("\n")[1:-1])

        with open(filepath, "w") as f:
            f.write(fixed_code)
            
        await ctx.send(f"✅ {filename} has been fixed and saved based on the Master Plan.")
    except Exception as e:
        await ctx.send(f"❌ Failed to fix: {e}")


if __name__ == "__main__":
    print("🚀 Starting JARVIS Discord Bot...")
    bot.run(TOKEN)