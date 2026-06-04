import json, os, discord

def load(f):
    return json.load(open(f, encoding='utf-8')) if os.path.exists(f) else {}

def save(f, d):
    json.dump(d, open(f, 'w', encoding='utf-8'), indent=2)

def ok(title, desc=None, color=discord.Color.green()):
    return discord.Embed(title=f"✅ {title}", description=desc, color=color)

def err(desc):
    return discord.Embed(title="❌ Error", description=desc, color=discord.Color.red())

def info(title, desc=None, color=discord.Color.blue()):
    return discord.Embed(title=title, description=desc, color=color)

MEDALS = ['🥇','🥈','🥉']

def medal(i):
    return MEDALS[i] if i < 3 else f"**{i+1}.**"

def rank_class(i):
    return ['gold','silver','bronze'][i] if i < 3 else ''
