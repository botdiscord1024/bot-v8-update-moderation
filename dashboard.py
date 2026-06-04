from flask import Flask, render_template_string, current_app, request, jsonify, redirect, url_for
import json
import os

app = Flask(__name__)

def load(f):
    return json.load(open(f, encoding='utf-8')) if os.path.exists(f) else {}

def save(f, d):
    json.dump(d, open(f, 'w', encoding='utf-8'), indent=2)

def xp_for_level(level):
    return 5 * (level ** 2) + 50 * level + 100

def total_xp_for_level(level):
    return sum(xp_for_level(i) for i in range(level))

def get_level_from_xp(xp):
    level = 0
    while xp >= total_xp_for_level(level + 1):
        level += 1
        if level > 500: 
            break
    return level

def get_gid():
    bot = current_app.config.get('BOT')
    if bot and hasattr(bot, 'cached_data'):
        for key in ['moderation', 'levels', 'counting', 'story', 'welcomer', 'youtube']:
            d = bot.cached_data.get(key, {})
            if d:
                return list(d.keys())[0]
    return None

def resolve_name(uid, lvl_data):
    bot = current_app.config.get('BOT')
    if uid in lvl_data and 'name' in lvl_data[uid]:
        return lvl_data[uid]['name']
    if bot:
        user = bot.get_user(int(uid))
        if user: 
            return user.display_name
    return f"User {uid}"

def render(route, title, desc, body):
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
      <title>{{ title }}</title>
      <link href="https://fonts.googleapis.com/css2?family=GG+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
      <style>
        :root { --b-dark: #1e1f22; --b-mid: #2b2d31; --b-light: #313338; --b-nav: #111214; --accent: #5865f2; --text: #f2f3f5; --sub: #b5bac1; }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'GG Sans', sans-serif; }
        body { display: flex; height: 100vh; background: var(--b-dark); color: var(--text); overflow: hidden; }
        
        .sidebar { width: 260px; background: var(--b-nav); padding: 24px 12px; display: flex; flex-direction: column; gap: 4px; }
        .brand { font-size: 18px; font-weight: 700; padding: 0 12px 20px 12px; border-bottom: 1px solid #2e3035; margin-bottom: 16px; color: #fff; }
        .nav-item { display: flex; align-items: center; padding: 10px 12px; border-radius: 4px; color: var(--sub); text-decoration: none; font-size: 14px; font-weight: 500; transition: .15s; }
        .nav-item:hover { background: #35373c; color: #fff; }
        .nav-item.active { background: var(--accent); color: #fff; }
        
        .main { flex: 1; display: flex; flex-direction: column; height: 100vh; background: var(--b-dark); }
        .header { background: var(--b-mid); padding: 20px 32px; border-bottom: 1px solid #1f2023; }
        .header h1 { font-size: 24px; font-weight: 700; color: #fff; }
        .header p { font-size: 14px; color: var(--sub); margin-top: 4px; }
        
        .content { flex: 1; padding: 32px; overflow-y: auto; }
        .card { background: var(--b-mid); border-radius: 8px; border: 1px solid #232428; padding: 24px; margin-bottom: 24px; }
        .card-header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #3f4248; padding-bottom: 16px; margin-bottom: 20px; }
        .card-header h3 { font-size: 18px; color: #fff; }
        .card-header p { font-size: 13px; color: var(--sub); margin-top: 2px; }
        
        /* Form Controls */
        .field { margin-bottom: 20px; }
        .field label { display: block; font-size: 12px; font-weight: 700; color: var(--sub); text-transform: uppercase; margin-bottom: 8px; }
        .field input, .field select, .field textarea { width: 100%; background: var(--b-dark); border: 1px solid #111214; padding: 10px; border-radius: 4px; color: #fff; font-size: 14px; }
        .field input:focus, .field select:focus, .field textarea:focus { border-color: var(--accent); outline: none; }
        
        /* Toggles */
        .toggle-row { display: flex; justify-content: space-between; align-items: center; padding: 16px 0; border-bottom: 1px solid #2e3035; }
        .toggle-row:last-child { border-bottom: none; }
        .toggle-info h4 { margin: 0; font-size: 15px; color: #fff; }
        .toggle-info p { margin: 4px 0 0 0; font-size: 13px; color: var(--sub); }
        .toggle { position: relative; display: inline-block; width: 48px; height: 26px; }
        .toggle input { opacity: 0; width: 0; height: 0; }
        .toggle-slider { position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: #4e5058; transition: .2s; border-radius: 34px; }
        .toggle-slider:before { position: absolute; content: ""; height: 18px; width: 18px; left: 4px; bottom: 4px; background-color: white; transition: .2s; border-radius: 50%; }
        input:checked + .toggle-slider { background-color: #23a55a; }
        input:checked + .toggle-slider:before { transform: translateX(22px); }
        
        /* Leaderboards & Lists */
        .lb-row { display: flex; justify-content: space-between; align-items: center; padding: 12px; background: var(--b-light); border-radius: 4px; margin-bottom: 8px; }
        .lb-name { display: flex; align-items: center; font-size: 14px; }
        .lb-val { font-size: 14px; color: var(--sub); font-weight: 600; }
        .lb-empty { text-align: center; color: var(--sub); padding: 20px; font-size: 14px; }
        
        .btn { display: inline-block; background: var(--accent); color: #fff; border: none; padding: 10px 20px; border-radius: 4px; font-size: 14px; font-weight: 500; cursor: pointer; transition: .15s; text-decoration: none; }
        .btn:hover { background: #4752c4; }
        .btn-primary { background: var(--accent); }
        .btn-save-row { display: flex; justify-content: flex-end; margin-top: 12px; }
      </style>
      <script>
        function testMessage(moduleName, msgType) {
            fetch('/api/test_message', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ module: moduleName, type: msgType })
            }).then(() => alert('🔔 Тестовото съобщение беше изпратено!'));
        }
      </script>
    </head>
    <body>
      <div class="sidebar">
        <div class="brand">👑 Admin Panel</div>
        <a href="/moderation" class="nav-item {% if route=='moderation' %}active{% endif %}">🛡️ Moderation</a>
        <a href="/welcomer" class="nav-item {% if route=='welcomer' %}active{% endif %}">👋 Welcomer</a>
        <a href="/levels" class="nav-item {% if route=='levels' %}active{% endif %}">⭐ Leveling System</a>
        <a href="/counting" class="nav-item {% if route=='counting' %}active{% endif %}">🔢 Counting Game</a>
        <a href="/ai-settings" class="nav-item {% if route=='ai-settings' %}active{% endif %}">🤖 AI Assistant</a>
        <a href="/daily-modules" class="nav-item {% if route=='daily-modules' %}active{% endif %}">📆 Daily Modules</a>
        <a href="/youtube" class="nav-item {% if route=='youtube' %}active{% endif %}">📺 YouTube Alerts</a>
        <a href="/story" class="nav-item {% if route=='story' %}active{% endif %}">📖 Story Mode</a>
      </div>
      <div class="main">
        <div class="header">
          <h1>{{ title }}</h1>
          <p>{{ desc }}</p>
        </div>
        <div class="content">
          {{ body|safe }}
        </div>
      </div>
    </body>
    </html>
    """, route=route, title=title, desc=desc, body=body)

# ══════════════════════════════════════════════════════════
#  TEST MESSAGE API (NEW)
# ══════════════════════════════════════════════════════════
@app.route('/api/test_message', methods=['POST'])
def api_test_message():
    data = request.json
    bot = current_app.config.get('BOT')
    if bot and hasattr(bot, 'trigger_test_message'):
        bot.trigger_test_message(data)
    return jsonify({'ok': True})

# ══════════════════════════════════════════════════════════
#  MODERATION PAGE
# ══════════════════════════════════════════════════════════
@app.route('/')
@app.route('/moderation')
def moderation():
    gid = get_gid() or 'default'
    cfg = load('config.json').get(gid, {})
    
    automod_on = 'checked' if cfg.get('automod_enabled', False) else ''
    invite_block_on = 'checked' if cfg.get('block_invites', False) else ''
    banned_words = cfg.get('banned_words', "")
    log_channel = cfg.get('log_channel', "")
    
    body = f"""
    <form id="modForm" onsubmit="saveMod(event)">
    <div class="card">
      <div class="card-header"><div><h3>Auto-Moderation</h3><p>Configure automated filter rules</p></div></div>
      <div class="card-body">
        <div class="toggle-row">
          <div class="toggle-info"><h4>Enable Word Filter (AutoMod)</h4><p>Scan and delete messages containing blacklisted phrases</p></div>
          <label class="toggle"><input type="checkbox" id="automod_enabled" {automod_on}> <span class="toggle-slider"></span></label>
        </div>
        <div class="toggle-row">
          <div class="toggle-info"><h4>Block Server Invites</h4><p>Automatically remove raw Discord server invitation links</p></div>
          <label class="toggle"><input type="checkbox" id="block_invites" {invite_block_on}> <span class="toggle-slider"></span></label>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-header"><div><h3>Logging & Blacklists</h3><p>Manage system logging channels and terms</p></div></div>
      <div class="card-body">
        <div class="field"><label>Mod Log Channel ID</label><input type="text" id="log_channel" value="{log_channel}" placeholder="123456789012345678"></div>
        <div class="field"><label>Banned Words List (comma separated)</label><textarea id="banned_words" rows="3" placeholder="badword1, badword2, toxic">{banned_words}</textarea></div>
      </div>
    </div>
    <div class="btn-save-row"><button type="submit" class="btn btn-primary">Save Moderation Config</button></div>
    </form>

    <div id="toast_mod" style="display:none;position:fixed;bottom:24px;right:24px;background:#23a55a;color:#fff;padding:12px 20px;border-radius:6px;font-weight:600;font-size:14px;z-index:9999;">✅ Moderation configs saved successfully!</div>

    <script>
    function saveMod(e){{
      e.preventDefault();
      fetch('/api/moderation/save', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{
          automod_enabled: document.getElementById('automod_enabled').checked,
          block_invites: document.getElementById('block_invites').checked,
          log_channel: document.getElementById('log_channel').value,
          banned_words: document.getElementById('banned_words').value
        }})
      }}).then(() => {{
         var t = document.getElementById('toast_mod'); t.style.display='block'; setTimeout(()=>t.style.display='none',2500);
      }});
    }}
    </script>
    """
    return render('moderation', '🛡️ Moderation Settings', 'Control automod configurations, blacklisted word definitions, and execution protocols', body)

@app.route('/api/moderation/save', methods=['POST'])
def api_moderation_save():
    gid = get_gid() or 'default'
    cfg = load('config.json')
    cfg.setdefault(gid, {}).update(request.json)
    save('config.json', cfg)
    import builtins
    if hasattr(builtins, 'refresh_bot_cache'): 
        builtins.refresh_bot_cache()
    return jsonify({'ok': True})

# ══════════════════════════════════════════════════════════
#  WELCOMER PAGE
# ══════════════════════════════════════════════════════════
@app.route('/welcomer')
def welcomer():
    gid = get_gid() or 'default'
    cfg = load('config.json').get(gid, {})
    w_cfg = cfg.get('welcomer', {})
    
    enabled = 'checked' if w_cfg.get('enabled', False) else ''
    welcome_enabled = 'checked' if w_cfg.get('welcome_enabled', False) else ''
    embed_enabled = 'checked' if w_cfg.get('embed_enabled', False) else ''
    autorole_enabled = 'checked' if w_cfg.get('autorole_enabled', False) else ''
    dm_enabled = 'checked' if w_cfg.get('dm_enabled', False) else ''
    
    channel = w_cfg.get('channel', '')
    message = w_cfg.get('message', 'Hello {user.mention}, welcome to **{server.name}**! 🎉')
    embed_title = w_cfg.get('embed_title', '👋 New Member Joined!')
    embed_color = w_cfg.get('embed_color', '#5865f2')
    autorole_roles = w_cfg.get('autorole_roles', '')
    dm_message = w_cfg.get('dm_message', 'Hey there! We are thrilled to have you join us at {server.name}!')

    leave_enabled = 'checked' if w_cfg.get('leave_enabled', False) else ''
    leave_embed_enabled = 'checked' if w_cfg.get('leave_embed_enabled', False) else ''
    leave_channel = w_cfg.get('leave_channel', '')
    leave_message = w_cfg.get('leave_message', 'Member **{user.name}** left the server. We now have **{member_count}** total members. 😢')
    leave_embed_title = w_cfg.get('leave_embed_title', '😢 A Member Left')
    leave_embed_color = w_cfg.get('leave_embed_color', '#f23f43')

    body = f"""
    <form id="welcomeForm" onsubmit="saveWelcome(event)">
    <div class="card" style="margin-bottom: 24px; border-left: 4px solid #5865f2;">
      <div class="card-body" style="padding: 20px;">
        <div class="toggle-row" style="margin: 0;">
          <div class="toggle-info">
            <h3 style="margin: 0 0 4px 0; color: #fff;">⚙️ Global Module Status</h3>
            <p style="margin: 0; font-size: 13px; color: #b5bac1;">Enable or disable the entire Welcomer & Leave system instantly</p>
          </div>
          <label class="toggle"><input type="checkbox" id="m_enabled" {enabled}> <span class="toggle-slider"></span></label>
        </div>
      </div>
    </div>

    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 24px;">
      <div>
        <div class="card">
          <div class="card-header"><div><h3>👋 Welcome Greetings</h3><p>Configure automated greetings for new members</p></div></div>
          <div class="card-body">
            <div class="toggle-row">
              <div class="toggle-info"><h4>Enable Welcome Messages</h4><p>Greet new members automatically when they join</p></div>
              <label class="toggle"><input type="checkbox" id="w_enabled" {welcome_enabled}> <span class="toggle-slider"></span></label>
            </div>
            <div class="field" style="margin-top:20px;">
              <label>Welcome Channel ID</label>
              <input type="text" id="w_channel" value="{channel}" placeholder="123456789012345678">
            </div>
            <div class="field">
              <label>Plain Text / Embed Description Message</label>
              <textarea id="w_message" rows="3">{message}</textarea>
              <p style="font-size:12px;color:#b5bac1;margin-top:4px;">Placeholders: <code style="color:#5865f2;">{{user.mention}}</code>, <code style="color:#5865f2;">{{user.name}}</code>, <code style="color:#5865f2;">{{server.name}}</code>, <code style="color:#5865f2;">{{member_count}}</code></p>
            </div>
            <button type="button" class="btn" style="background:#4752c4; margin-top:10px;" onclick="testMessage('welcomer', 'welcome')">🔔 Test Welcome Message</button>
          </div>
        </div>

        <div class="card">
          <div class="card-header"><div><h3>✨ Premium Embed Customization</h3><p>Make your welcome greetings stand out with beautiful rich embeds</p></div></div>
          <div class="card-body">
            <div class="toggle-row">
              <div class="toggle-info"><h4>Use Embed Layout</h4><p>Deliver the message inside a beautifully structured Discord Embed card</p></div>
              <label class="toggle"><input type="checkbox" id="w_embed_enabled" {embed_enabled}> <span class="toggle-slider"></span></label>
            </div>
            <div style="display:grid;grid-template-columns:2fr 1fr;gap:16px;margin-top:20px;">
              <div class="field">
                <label>Embed Title</label>
                <input type="text" id="w_embed_title" value="{embed_title}">
              </div>
              <div class="field">
                <label>Embed Sidebar Color (Hex)</label>
                <input type="text" id="w_embed_color" value="{embed_color}" placeholder="#5865f2">
              </div>
            </div>
          </div>
        </div>

        <div class="card">
          <div class="card-header"><div><h3>🚀 Auto-Role & Direct Messages</h3><p>Automate onboarding with instantaneous roles and direct delivery notes</p></div></div>
          <div class="card-body">
            <div class="toggle-row">
              <div class="toggle-info"><h4>Enable Auto-Role (On Join)</h4><p>Assign specialized server roles automatically when someone arrives</p></div>
              <label class="toggle"><input type="checkbox" id="w_autorole_enabled" {autorole_enabled}> <span class="toggle-slider"></span></label>
            </div>
            <div class="field" style="margin-top:20px;">
              <label>Target Role IDs (Comma-separated for multiples)</label>
              <input type="text" id="w_autorole_roles" value="{autorole_roles}" placeholder="123456789012345678">
            </div>
            <hr style="border:none;border-top:1px solid #2e3035;margin:20px 0;">
            <div class="toggle-row">
              <div class="toggle-info"><h4>Send DM on Join</h4><p>Transmit an automated onboarding message straight to the user's private messages</p></div>
              <label class="toggle"><input type="checkbox" id="w_dm_enabled" {dm_enabled}> <span class="toggle-slider"></span></label>
            </div>
            <div class="field" style="margin-top:20px;">
              <label>Private Message Template Text</label>
              <textarea id="w_dm_message" rows="3">{dm_message}</textarea>
            </div>
          </div>
        </div>
      </div>

      <div>
        <div class="card">
          <div class="card-header"><div><h3>😢 Leave Logger</h3><p>Configure automated leave messages for departing members</p></div></div>
          <div class="card-body">
            <div class="toggle-row">
              <div class="toggle-info"><h4>Enable Leave Messages</h4><p>Log or announce when members leave the server</p></div>
              <label class="toggle"><input type="checkbox" id="w_leave_enabled" {leave_enabled}> <span class="toggle-slider"></span></label>
            </div>
            <div class="field" style="margin-top:20px;">
              <label>Leave Channel ID</label>
              <input type="text" id="w_leave_channel" value="{leave_channel}" placeholder="123456789012345678">
            </div>
            <div class="field">
              <label>Plain Text / Embed Description Message</label>
              <textarea id="w_leave_message" rows="3">{leave_message}</textarea>
              <p style="font-size:12px;color:#b5bac1;margin-top:4px;">Placeholders: <code style="color:#5865f2;">{{user.name}}</code>, <code style="color:#5865f2;">{{server.name}}</code>, <code style="color:#5865f2;">{{member_count}}</code></p>
            </div>
            <button type="button" class="btn" style="background:#da373c; margin-top:10px;" onclick="testMessage('welcomer', 'leave')">🔔 Test Leave Message</button>
          </div>
        </div>

        <div class="card">
          <div class="card-header"><div><h3>✨ Leave Embed Customization</h3><p>Make your departure notifications look professional</p></div></div>
          <div class="card-body">
            <div class="toggle-row">
              <div class="toggle-info"><h4>Use Embed Layout for Leave</h4><p>Deliver the leave notice inside a structured Discord Embed card</p></div>
              <label class="toggle"><input type="checkbox" id="w_leave_embed_enabled" {leave_embed_enabled}> <span class="toggle-slider"></span></label>
            </div>
            <div style="display:grid;grid-template-columns:2fr 1fr;gap:16px;margin-top:20px;">
              <div class="field">
                <label>Embed Title</label>
                <input type="text" id="w_leave_embed_title" value="{leave_embed_title}">
              </div>
              <div class="field">
                <label>Embed Sidebar Color (Hex)</label>
                <input type="text" id="w_leave_embed_color" value="{leave_embed_color}" placeholder="#f23f43">
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
    
    <div class="btn-save-row"><button type="submit" class="btn btn-primary">Save Module Configurations</button></div>
    </form>

    <div id="toast_welcome" style="display:none;position:fixed;bottom:24px;right:24px;background:#23a55a;color:#fff;padding:12px 20px;border-radius:6px;font-weight:600;font-size:14px;z-index:9999;">✅ Configurations saved successfully!</div>

    <script>
    function saveWelcome(e){{
      e.preventDefault();
      fetch('/api/welcomer/save', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{
          enabled: document.getElementById('m_enabled').checked,
          welcome_enabled: document.getElementById('w_enabled').checked,
          channel: document.getElementById('w_channel').value,
          message: document.getElementById('w_message').value,
          embed_enabled: document.getElementById('w_embed_enabled').checked,
          embed_title: document.getElementById('w_embed_title').value,
          embed_color: document.getElementById('w_embed_color').value,
          autorole_enabled: document.getElementById('w_autorole_enabled').checked,
          autorole_roles: document.getElementById('w_autorole_roles').value,
          dm_enabled: document.getElementById('w_dm_enabled').checked,
          dm_message: document.getElementById('w_dm_message').value,
          
          leave_enabled: document.getElementById('w_leave_enabled').checked,
          leave_channel: document.getElementById('w_leave_channel').value,
          leave_message: document.getElementById('w_leave_message').value,
          leave_embed_enabled: document.getElementById('w_leave_embed_enabled').checked,
          leave_embed_title: document.getElementById('w_leave_embed_title').value,
          leave_embed_color: document.getElementById('w_leave_embed_color').value
        }})
      }}).then(() => {{
         var t = document.getElementById('toast_welcome'); t.style.display='block'; setTimeout(()=>t.style.display='none',2500);
      }});
    }}
    </script>
    """
    return render('welcomer', '👋 Welcomer & Leave Module', 'Handle custom greeting cards, leave trackers, join workflows, and onboarding configurations', body)

@app.route('/api/welcomer/save', methods=['POST'])
def api_welcomer_save():
    gid = get_gid() or 'default'
    cfg = load('config.json')
    cfg.setdefault(gid, {}).update(request.json)
    save('config.json', cfg)
    import builtins
    if hasattr(builtins, 'refresh_bot_cache'): 
        builtins.refresh_bot_cache()
    return jsonify({'ok': True})

# ══════════════════════════════════════════════════════════
#  LEVELING PAGE
# ══════════════════════════════════════════════════════════
@app.route('/levels')
def levels():
    gid = get_gid() or 'default'
    cfg = load('config.json').get(gid, {})
    
    lvl_msg_on = 'checked' if cfg.get('enable_levelup_message', True) else ''
    vc_xp_on = 'checked' if cfg.get('enable_voice_xp', True) else ''
    
    type_opt = cfg.get('levelup_type', 'channel')
    opts = f"""
    <option value="channel" {'selected' if type_opt=='channel' else ''}>Specific Channel</option>
    <option value="current" {'selected' if type_opt=='current' else ''}>Current Channel</option>
    <option value="dm" {'selected' if type_opt=='dm' else ''}>Direct Message (DM)</option>
    <option value="disabled" {'selected' if type_opt=='disabled' else ''}>Disabled</option>
    """
    
    msg_val = cfg.get('levelup_message', "GG {{user.mention}}! You just leveled up to **Level {{level}}**!")
    ch_val = cfg.get('level_channel', "")
    
    # NEW: XP Rate & Level Roles
    xp_rate = cfg.get('xp_rate', 1.0)
    level_roles = json.dumps(cfg.get('level_roles', {}), indent=2)

    lvl_data = load('levels.json').get(gid, {})
    sorted_users = sorted(lvl_data.items(), key=lambda x: x[1].get('xp', 0) if isinstance(x[1], dict) else x[1], reverse=True)[:10]
    
    lb_rows = ""
    for rank, (uid, data) in enumerate(sorted_users, 1):
        xp = data.get('xp', 0) if isinstance(data, dict) else data
        lvl = get_level_from_xp(xp)
        name = resolve_name(uid, lvl_data)
        lb_rows += f"""
        <div class="lb-row">
            <div class="lb-name"><b>#{rank}</b> &nbsp; {name}</div>
            <div class="lb-val">Lvl {lvl} &nbsp;<span style="color:#4e5058;font-weight:normal;">({xp} XP)</span></div>
        </div>"""
    if not lb_rows:
        lb_rows = '<div class="lb-empty">No level data available yet.</div>'

    body = f"""
    <form id="lvlForm" onsubmit="saveLvl(event)">
    <div class="card">
      <div class="card-header"><div><h3>General Settings</h3><p>Configure automated level alerts and behaviors</p></div></div>
      <div class="card-body">
        <div class="toggle-row">
          <div class="toggle-info"><h4>Level Up Messages</h4><p>Enable announcements when server members level up</p></div>
          <label class="toggle"><input type="checkbox" id="enable_levelup_message" {lvl_msg_on}> <span class="toggle-slider"></span></label>
        </div>
        <div class="toggle-row">
          <div class="toggle-info"><h4>Voice Channel XP</h4><p>Award XP passively to members active in voice chats</p></div>
          <label class="toggle"><input type="checkbox" id="enable_voice_xp" {vc_xp_on}> <span class="toggle-slider"></span></label>
        </div>
      </div>
    </div>

    <!-- NEW: Level Roles & XP Rate -->
    <div class="card">
      <div class="card-header"><div><h3>XP Multiplier & Level Roles</h3><p>Adjust how fast members level up and automatic role rewards</p></div></div>
      <div class="card-body">
        <div class="field">
          <label>Global XP Multiplier (Default 1.0)</label>
          <input type="number" step="0.1" id="xp_rate" value="{xp_rate}">
        </div>
        <div class="field">
          <label>Level Role Mapping (JSON Format: {{"Level": "RoleID"}})</label>
          <textarea id="level_roles" rows="4" placeholder='{{"10": "123456789012345678", "20": "987654321098765432"}}'>{level_roles}</textarea>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-header"><div><h3>Alert Behavior & Templates</h3><p>Customize where and how leveling up is displayed</p></div></div>
      <div class="card-body">
        <div class="field"><label>Alert Destination</label><select id="levelup_type">{opts}</select></div>
        <div class="field"><label>Target Channel ID (Only if Specific Channel is active)</label><input type="text" id="level_channel" value="{ch_val}" placeholder="123456789012345678"></div>
        <div class="field"><label>Custom Announcement Message</label><textarea id="levelup_message" rows="3">{msg_val}</textarea></div>
        <button type="button" class="btn" style="background:#4752c4; margin-top:10px;" onclick="testMessage('levels', 'levelup')">🔔 Test Level Up Message</button>
      </div>
    </div>
    
    <div class="btn-save-row"><button type="submit" class="btn btn-primary">Save Configuration</button></div>
    </form>

    <div class="card" style="margin-top:24px">
      <div class="card-header"><h3>🏆 Server Top 10 Leaderboard</h3></div>
      <div class="card-body">{lb_rows}</div>
    </div>

    <div id="toast" style="display:none;position:fixed;bottom:24px;right:24px;background:#23a55a;color:#fff;padding:12px 20px;border-radius:6px;font-weight:600;font-size:14px;z-index:9999;">✅ Leveling configs saved successfully!</div>

    <script>
    function saveLvl(e){{
      e.preventDefault();
      
      let parsedRoles = {{}};
      try {{
          let roleVal = document.getElementById('level_roles').value;
          if (roleVal.trim() !== '') parsedRoles = JSON.parse(roleVal);
      }} catch(err) {{
          alert("Invalid JSON format in Level Roles! Please check it.");
          return;
      }}

      fetch('/api/levels/save', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{
          enable_levelup_message: document.getElementById('enable_levelup_message').checked,
          enable_voice_xp: document.getElementById('enable_voice_xp').checked,
          levelup_type: document.getElementById('levelup_type').value,
          level_channel: document.getElementById('level_channel').value,
          levelup_message: document.getElementById('levelup_message').value,
          xp_rate: parseFloat(document.getElementById('xp_rate').value) || 1.0,
          level_roles: parsedRoles
        }})
      }}).then(() => {{
         var t = document.getElementById('toast'); t.style.display='block'; setTimeout(()=>t.style.display='none',2500);
      }});
    }}
    </script>
    """
    return render('levels', '⭐ Leveling System', 'Manage configurations and track active user XP records', body)

@app.route('/api/levels/save', methods=['POST'])
def api_levels_save():
    gid = get_gid() or 'default'
    cfg = load('config.json')
    cfg.setdefault(gid, {}).update(request.json)
    save('config.json', cfg)
    import builtins
    if hasattr(builtins, 'refresh_bot_cache'): 
        builtins.refresh_bot_cache()
    return jsonify({'ok': True})

# ══════════════════════════════════════════════════════════
#  COUNTING GAME PAGE
# ══════════════════════════════════════════════════════════
@app.route('/counting')
def counting():
    gid = get_gid() or 'default'
    c_data = load('counting.json').get(gid, {})
    
    current_count = c_data.get('count', 0)
    high_score = c_data.get('high_score', 0)
    
    counting_on = 'checked' if c_data.get('enabled', False) else ''
    same_user_on = 'checked' if c_data.get('allow_same_user', False) else ''
    shame_role_on = 'checked' if c_data.get('shame_role', False) else ''
    delete_invalid_on = 'checked' if c_data.get('delete_invalid', False) else ''
    
    ch_val = c_data.get('channel', "") or ""
    shame_name_val = c_data.get('shame_role_name', "💀 Count Ruiner")

    body = f"""
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:24px;margin-bottom:24px;">
      <div class="card" style="margin:0; text-align:center;">
        <h4 style="color:#b5bac1;text-transform:uppercase;font-size:12px;letter-spacing:1px;">Current Counter</h4>
        <h1 style="font-size:48px;color:#5865f2;margin-top:10px;">{current_count}</h1>
      </div>
      <div class="card" style="margin:0; text-align:center;">
        <h4 style="color:#b5bac1;text-transform:uppercase;font-size:12px;letter-spacing:1px;">Server High Score</h4>
        <h1 style="font-size:48px;color:#23a55a;margin-top:10px;">{high_score}</h1>
      </div>
    </div>

    <form id="countingForm" onsubmit="saveCounting(event)">
    <div class="card">
      <div class="card-header"><div><h3>Game Execution Channels</h3><p>Configure channel binding and system automation state</p></div></div>
      <div class="card-body">
        <div class="toggle-row">
          <div class="toggle-info"><h4>Enable Counting Game</h4><p>Toggle the mathematics simulation module status</p></div>
          <label class="toggle"><input type="checkbox" id="counting_enabled" {counting_on}> <span class="toggle-slider"></span></label>
        </div>
        <div class="field" style="margin-top:20px;">
          <label>Counting Channel ID</label>
          <input type="text" id="counting_channel" value="{ch_val}" placeholder="123456789012345678">
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-header"><div><h3>Gameplay & Restriction Mechanics</h3><p>Manage restriction logic and anti-spam protocols</p></div></div>
      <div class="card-body">
        <div class="toggle-row">
          <div class="toggle-info"><h4>Allow Consecutive Counting</h4><p>Can a single individual submit two values in a row?</p></div>
          <label class="toggle"><input type="checkbox" id="allow_same_user" {same_user_on}> <span class="toggle-slider"></span></label>
        </div>
        <div class="toggle-row">
          <div class="toggle-info"><h4>Enforce Shame Mute (Block on Fail)</h4><p>Give shame role and block user from counting until removed</p></div>
          <label class="toggle"><input type="checkbox" id="shame_role" {shame_role_on}> <span class="toggle-slider"></span></label>
        </div>
        <div class="toggle-row">
          <div class="toggle-info"><h4>Auto-Clean Chat (Delete Invalid Messages)</h4><p>Instantly remove general chatter or wrong submissions to keep channel clean</p></div>
          <label class="toggle"><input type="checkbox" id="delete_invalid" {delete_invalid_on}> <span class="toggle-slider"></span></label>
        </div>
        
        <div class="field" style="margin-top:20px;">
          <label>Shame Role Designation Name</label>
          <input type="text" id="shame_role_name" value="{shame_name_val}" placeholder="💀 Count Ruiner">
        </div>
      </div>
    </div>
    
    <div class="btn-save-row"><button type="submit" class="btn btn-primary">Save Counting Configurations</button></div>
    </form>

    <div id="toast_count" style="display:none;position:fixed;bottom:24px;right:24px;background:#23a55a;color:#fff;padding:12px 20px;border-radius:6px;font-weight:600;font-size:14px;z-index:9999;">✅ Counting configs updated and live!</div>

    <script>
    function saveCounting(e){{
      e.preventDefault();
      fetch('/api/counting/save', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{
          enabled: document.getElementById('counting_enabled').checked,
          channel: document.getElementById('counting_channel').value,
          allow_same_user: document.getElementById('allow_same_user').checked,
          shame_role: document.getElementById('shame_role').checked,
          delete_invalid: document.getElementById('delete_invalid').checked,
          shame_role_name: document.getElementById('shame_role_name').value
        }})
      }}).then(() => {{
         var t = document.getElementById('toast_count'); t.style.display='block'; setTimeout(()=>t.style.display='none',2500);
      }});
    }}
    </script>
    """
    return render('counting', '🔢 Counting System', 'Real-time synchronization data tracking counting parameters', body)

@app.route('/api/counting/save', methods=['POST'])
def api_counting_save():
    gid = get_gid() or 'default'
    cfg = load('counting.json')
    cfg.setdefault(gid, {}).update(request.json)
    save('counting.json', cfg)
    import builtins
    if hasattr(builtins, 'refresh_bot_cache'): 
        builtins.refresh_bot_cache()
    return jsonify({'ok': True})

# ══════════════════════════════════════════════════════════
#  AI SETTINGS & CUSTOM EMOJIS
# ══════════════════════════════════════════════════════════
@app.route('/ai-settings')
def ai_settings():
    gid = get_gid() or 'default'
    cfg = load('config.json').get(gid, {})
    
    ai_on = 'checked' if cfg.get('ai_enabled', True) else ''
    reply_on = 'checked' if cfg.get('ai_reply_on_mention', True) else ''
    emojis_on = 'checked' if cfg.get('ai_auto_emojis', True) else ''
    
    custom_emojis = cfg.get('custom_external_emojis', {})
    emoji_rows = ''
    for name, url in custom_emojis.items():
        emoji_rows += f"""
        <div class="lb-row">
            <div class="lb-name"><img src="{url}" style="width:24px;height:24px;border-radius:4px;margin-right:8px;vertical-align:middle"><b>:{name}:</b></div>
            <div class="lb-val"><button onclick="deleteEmoji('{name}')" style="background:#ed4245;color:white;border:none;padding:4px 8px;border-radius:4px;cursor:pointer">Remove</button></div>
        </div>"""
    if not emoji_rows:
        emoji_rows = '<div class="lb-empty">No custom external emojis added yet</div>'

    body = f"""
    <form id="aiForm" onsubmit="saveAiSettings(event)">
    <div class="card">
      <div class="card-header">
        <div><h3>AI Control Panel</h3><p>Manage the behavior of your bot's smart AI assistant</p></div>
        <label class="toggle"><input type="checkbox" id="ai_enabled" {ai_on}><span class="toggle-slider"></span></label>
      </div>
      <div class="card-body">
        <div class="toggle-row">
          <div class="toggle-info"><h4>Reply on Mention / Reply</h4><p>Should the AI answer when someone pings or replies to its messages?</p></div>
          <label class="toggle"><input type="checkbox" id="ai_reply_on_mention" {reply_on}><span class="toggle-slider"></span></label>
        </div>
        <div class="toggle-row">
          <div class="toggle-info"><h4>Auto Emoji Reactions</h4><p>Allow the AI to automatically place smart emojis on messages</p></div>
          <label class="toggle"><input type="checkbox" id="ai_auto_emojis" {emojis_on}><span class="toggle-slider"></span></label>
        </div>
      </div>
    </div>
    <div class="btn-save-row">
      <button type="submit" class="btn btn-primary">Save Settings</button>
    </div>
    </form>

    <div class="card" style="margin-top:24px">
      <div class="card-header"><h3>✨ Add External Emojis (Not in Discord Guild)</h3></div>
      <div class="card-body">
        <div style="display:grid;grid-template-columns:1fr 2fr;gap:12px;margin-bottom:12px">
          <div class="field"><label>Emoji Name</label><input type="text" id="em_name" placeholder="pepe_smile"></div>
          <div class="field"><label>Image URL (PNG/JPG Link)</label><input type="text" id="em_url" placeholder="https://example.com/image.png"></div>
        </div>
        <button onclick="addEmoji()" class="btn btn-primary" style="background:#57f287;color:black;font-weight:bold;">Add External Emoji</button>
        
        <div style="margin-top:20px">
            <h4>Current Custom External Emojis:</h4>
            {emoji_rows}
        </div>
      </div>
    </div>

    <div id="toast" style="display:none;position:fixed;bottom:24px;right:24px;background:#57f287;color:#000;padding:12px 20px;border-radius:6px;font-weight:600;font-size:14px;z-index:9999;">✅ Updated!</div>

    <script>
    function showToast(){{
      var t=document.getElementById('toast'); t.style.display='block'; setTimeout(()=>t.style.display='none',2500);
    }}
    function saveAiSettings(e){{
      e.preventDefault();
      fetch('/api/ai/save',{{
        method:'POST',
        headers:{{'Content-Type':'application/json'}},
        body:JSON.stringify({{
          ai_enabled: document.getElementById('ai_enabled').checked,
          ai_reply_on_mention: document.getElementById('ai_reply_on_mention').checked,
          ai_auto_emojis: document.getElementById('ai_auto_emojis').checked
        }})
      }}).then(()=>showToast());
    }}
    function addEmoji(){{
      var name = document.getElementById('em_name').value;
      var url = document.getElementById('em_url').value;
      if(!name || !url) return alert('Please fill both fields!');
      fetch('/api/ai/emoji/add',{{
        method:'POST',
        headers:{{'Content-Type':'application/json'}},
        body:JSON.stringify({{name:name, url:url}})
      }}).then(()=>location.reload());
    }}
    function deleteEmoji(name){{
      fetch('/api/ai/emoji/delete',{{
        method:'POST',
        headers:{{'Content-Type':'application/json'}},
        body:JSON.stringify({{name:name}})
      }}).then(()=>location.reload());
    }}
    </script>
    """
    return render('ai-settings', 'AI Assistant', 'Configure AI actions and external emojis', body)

@app.route('/api/ai/save', methods=['POST'])
def api_ai_save():
    gid = get_gid() or 'default'
    cfg = load('config.json')
    cfg.setdefault(gid, {}).update(request.json)
    save('config.json', cfg)
    import builtins
    if hasattr(builtins, 'refresh_bot_cache'): 
        builtins.refresh_bot_cache()
    return jsonify({'ok':True})

@app.route('/api/ai/emoji/add', methods=['POST'])
def api_ai_emoji_add():
    gid = get_gid() or 'default'
    cfg = load('config.json')
    cfg.setdefault(gid, {}).setdefault('custom_external_emojis', {})[request.json['name']] = request.json['url']
    save('config.json', cfg)
    import builtins
    if hasattr(builtins, 'refresh_bot_cache'): 
        builtins.refresh_bot_cache()
    return jsonify({'ok':True})

@app.route('/api/ai/emoji/delete', methods=['POST'])
def api_ai_emoji_delete():
    gid = get_gid() or 'default'
    cfg = load('config.json')
    if gid in cfg and 'custom_external_emojis' in cfg[gid]:
        cfg[gid]['custom_external_emojis'].pop(request.json['name'], None)
        save('config.json', cfg)
    import builtins
    if hasattr(builtins, 'refresh_bot_cache'): 
        builtins.refresh_bot_cache()
    return jsonify({'ok':True})

# ══════════════════════════════════════════════════════════
#  DAILY MODULES PAGE (FOTD, QOTD, ROTD, SOTD)
# ══════════════════════════════════════════════════════════
@app.route('/daily-modules')
def daily_modules():
    gid = get_gid() or 'default'
    cfg = load('config.json').get(gid, {})
    
    f_cfg = cfg.get('fotd_settings', {})
    q_cfg = cfg.get('qotd_settings', {})
    r_cfg = cfg.get('rotd_settings', {})
    s_cfg = cfg.get('sotd_settings', {})
    
    f_on = 'checked' if f_cfg.get('enabled', True) else ''
    q_on = 'checked' if q_cfg.get('enabled', True) else ''
    r_on = 'checked' if r_cfg.get('enabled', True) else ''
    s_on = 'checked' if s_cfg.get('enabled', True) else ''
    
    f_chan = f_cfg.get('channel_id', '')
    q_chan = q_cfg.get('channel_id', '')
    r_chan = r_cfg.get('channel_id', '')
    s_chan = s_cfg.get('channel_id', '')
    
    body = f"""
    <form id="dailyForm" onsubmit="saveDaily(event)">
      <!-- FOTD -->
      <div class="card">
        <div class="card-header">
          <div><h3>🧠 Fact Of The Day (FOTD)</h3><p>Automated interesting daily updates compiled by Gemini AI</p></div>
          <label class="toggle"><input type="checkbox" id="f_enabled" {f_on}><span class="toggle-slider"></span></label>
        </div>
        <div class="card-body">
          <div class="field"><label>Output Channel ID</label><input type="text" id="f_channel" value="{f_chan}" placeholder="123456789012345678"></div>
          <button type="button" class="btn" style="background:#4752c4;" onclick="testMessage('daily', 'fotd')">🔔 Test FOTD</button>
        </div>
      </div>

      <!-- QOTD -->
      <div class="card">
        <div class="card-header">
          <div><h3>❓ Question Of The Day (QOTD)</h3><p>Daily conversational engagement prompts for community topics</p></div>
          <label class="toggle"><input type="checkbox" id="q_enabled" {q_on}><span class="toggle-slider"></span></label>
        </div>
        <div class="card-body">
          <div class="field"><label>Output Channel ID</label><input type="text" id="q_channel" value="{q_chan}" placeholder="123456789012345678"></div>
          <button type="button" class="btn" style="background:#4752c4;" onclick="testMessage('daily', 'qotd')">🔔 Test QOTD</button>
        </div>
      </div>

      <!-- ROTD -->
      <div class="card">
        <div class="card-header">
          <div><h3>🧩 Riddle Of The Day (ROTD)</h3><p>Generate puzzling brain teasers dynamically every 24 hours</p></div>
          <label class="toggle"><input type="checkbox" id="r_enabled" {r_on}><span class="toggle-slider"></span></label>
        </div>
        <div class="card-body">
          <div class="field"><label>Output Channel ID</label><input type="text" id="r_channel" value="{r_chan}" placeholder="123456789012345678"></div>
          <button type="button" class="btn" style="background:#4752c4;" onclick="testMessage('daily', 'rotd')">🔔 Test ROTD</button>
        </div>
      </div>

      <!-- SOTD -->
      <div class="card">
        <div class="card-header">
          <div><h3>🎵 Song Of The Day (SOTD)</h3><p>Recommends gaming and rhythmic loops with high energy</p></div>
          <label class="toggle"><input type="checkbox" id="s_enabled" {s_on}><span class="toggle-slider"></span></label>
        </div>
        <div class="card-body">
          <div class="field"><label>Output Channel ID</label><input type="text" id="s_channel" value="{s_chan}" placeholder="123456789012345678"></div>
          <button type="button" class="btn" style="background:#4752c4;" onclick="testMessage('daily', 'sotd')">🔔 Test SOTD</button>
        </div>
      </div>

      <div class="btn-save-row"><button type="submit" class="btn btn-primary">Save Daily Modules</button></div>
    </form>

    <div id="toast_daily" style="display:none;position:fixed;bottom:24px;right:24px;background:#23a55a;color:#fff;padding:12px 20px;border-radius:6px;font-weight:600;font-size:14px;z-index:9999;">✅ Daily modules configurations saved!</div>

    <script>
    function saveDaily(e){{
      e.preventDefault();
      fetch('/api/daily-modules/save', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{
          fotd: {{ enabled: document.getElementById('f_enabled').checked, channel_id: document.getElementById('f_channel').value }},
          qotd: {{ enabled: document.getElementById('q_enabled').checked, channel_id: document.getElementById('q_channel').value }},
          rotd: {{ enabled: document.getElementById('r_enabled').checked, channel_id: document.getElementById('r_channel').value }},
          sotd: {{ enabled: document.getElementById('s_enabled').checked, channel_id: document.getElementById('s_channel').value }}
        }})
      }}).then(() => {{
         var t = document.getElementById('toast_daily'); t.style.display='block'; setTimeout(()=>t.style.display='none',2500);
      }});
    }}
    </script>
    """
    return render('daily-modules', '📆 Daily Automated Modules', 'Centralized configuration dashboard for managing cyclical broadcast integrations', body)

@app.route('/api/daily-modules/save', methods=['POST'])
def api_daily_modules_save():
    gid = get_gid() or 'default'
    cfg = load('config.json')
    data = request.json
    
    cfg.setdefault(gid, {}).setdefault('fotd_settings', {}).update(data['fotd'])
    cfg[gid].setdefault('qotd_settings', {}).update(data['qotd'])
    cfg[gid].setdefault('rotd_settings', {}).update(data['rotd'])
    cfg[gid].setdefault('sotd_settings', {}).update(data['sotd'])
    
    save('config.json', cfg)
    import builtins
    if hasattr(builtins, 'refresh_bot_cache'): 
        builtins.refresh_bot_cache()
    return jsonify({'ok': True})

# ══════════════════════════════════════════════════════════
#  YOUTUBE ALERTS PAGE
# ══════════════════════════════════════════════════════════
@app.route('/youtube')
def youtube():
    gid = get_gid() or 'default'
    bot = current_app.config.get('BOT')
    cache = getattr(bot, 'cached_data', {}) if bot else {}
    yt_data = cache.get('youtube', {}).get(gid, {})
    channels = yt_data.get('channels', {})

    # Build channel cards
    channel_cards = ''
    for cid, ch in channels.items():
        enabled = ch.get('enabled', True)
        status_color = '#23a55a' if enabled else '#ed4245'
        status_text  = 'Enabled' if enabled else 'Disabled'
        channel_cards += f'''
        <div class="card" style="border-left: 4px solid {status_color}; margin-bottom:16px;">
          <div class="card-header">
            <div>
              <h3>📺 {ch.get("name", cid)}</h3>
              <p>Channel ID: <code>{cid}</code> &nbsp;|&nbsp;
                 Status: <b style="color:{status_color}">{status_text}</b></p>
            </div>
            <div style="display:flex;gap:8px;">
              <button class="btn" style="background:#4e5058"
                onclick="testAlert('{cid}')">🧪 Test</button>
              <button class="btn" style="background:#ed4245"
                onclick="removeChannel('{cid}')">🗑️ Remove</button>
            </div>
          </div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">
            <div class="field">
              <label>Discord Alert Channel ID</label>
              <input type="text" id="dc_{cid}" value="{ch.get('discord_channel','')}"
                placeholder="Discord channel ID">
            </div>
            <div class="field">
              <label>Ping Role ID (optional)</label>
              <input type="text" id="role_{cid}" value="{ch.get('ping_role') or ''}"
                placeholder="Role ID to ping">
            </div>
            <div class="field" style="grid-column:span 2">
              <label>Custom Alert Message</label>
              <textarea id="msg_{cid}" rows="3"
                placeholder="Use {{author}}, {{title}}, {{url}}, {{channel}}"
                >{ch.get("message","🎬 **{{author}}** uploaded **{{title}}**\n{{url}}")}</textarea>
            </div>
          </div>
          <div style="display:flex;justify-content:space-between;align-items:center;margin-top:8px;">
            <label class="toggle">
              <input type="checkbox" {"checked" if enabled else ""}
                onchange="toggleChannel('{cid}', this.checked)">
              <span class="toggle-slider"></span>
            </label>
            <button class="btn" onclick="saveChannel('{cid}')">💾 Save Changes</button>
          </div>
        </div>'''

    if not channel_cards:
        channel_cards = '''<div class="lb-empty">
          No YouTube channels added yet.<br>
          Use <code>/youtube add &lt;channel_id&gt;</code> in Discord to add one.
        </div>'''

    body = f'''
    <div class="card">
      <div class="card-header">
        <div>
          <h3>📺 YouTube Alert Channels</h3>
          <p>Add channels with <code>/youtube add</code> in Discord. Checks for new videos every 10 minutes.</p>
        </div>
      </div>
      {channel_cards}
    </div>

    <div class="card">
      <div class="card-header"><h3>➕ Add New Channel</h3></div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">
        <div class="field">
          <label>YouTube Channel Link or @Handle</label>
          <input type="text" id="new_cid" placeholder="https://youtube.com/@ChannelName  or  @ChannelName  or  UCxxxxxxxx">
          <small style="color:#b5bac1;font-size:11px;">Paste any YouTube channel link, @handle, or Channel ID</small>
        </div>
        <div class="field">
          <label>Friendly Name</label>
          <input type="text" id="new_name" placeholder="e.g. Loot Gaming">
        </div>
        <div class="field">
          <label>Discord Channel ID</label>
          <input type="text" id="new_dc" placeholder="Discord text channel ID">
        </div>
        <div class="field">
          <label>Ping Role ID (optional)</label>
          <input type="text" id="new_role" placeholder="Leave empty for no ping">
        </div>
        <div class="field" style="grid-column:span 2">
          <label>Custom Alert Message</label>
          <textarea id="new_msg" rows="3">🎬 **{{author}}** just uploaded **{{title}}**!
{{url}}</textarea>
        </div>
      </div>
      <div class="btn-save-row">
        <button class="btn" onclick="addChannel()">➕ Add Channel</button>
      </div>
      <div id="add_status" style="margin-top:8px;font-size:13px;"></div>
    </div>

    <script>
    function saveChannel(cid) {{
      fetch('/api/youtube/save', {{
        method: 'POST',
        headers: {{'Content-Type':'application/json'}},
        body: JSON.stringify({{
          channel_id: cid,
          discord_channel: document.getElementById('dc_'+cid).value,
          ping_role: document.getElementById('role_'+cid).value || null,
          message: document.getElementById('msg_'+cid).value
        }})
      }}).then(r=>r.json()).then(d=>{{ if(d.ok) location.reload(); }});
    }}
    function toggleChannel(cid, val) {{
      fetch('/api/youtube/toggle', {{
        method: 'POST',
        headers: {{'Content-Type':'application/json'}},
        body: JSON.stringify({{channel_id: cid, enabled: val}})
      }});
    }}
    function removeChannel(cid) {{
      if(!confirm('Remove this YouTube alert?')) return;
      fetch('/api/youtube/remove', {{
        method: 'POST',
        headers: {{'Content-Type':'application/json'}},
        body: JSON.stringify({{channel_id: cid}})
      }}).then(()=>location.reload());
    }}
    function testAlert(cid) {{
      fetch('/api/youtube/test', {{
        method: 'POST',
        headers: {{'Content-Type':'application/json'}},
        body: JSON.stringify({{channel_id: cid}})
      }}).then(r=>r.json()).then(d=>alert(d.msg || 'Test sent!'));
    }}
    function addChannel() {{
      var status = document.getElementById('add_status');
      status.textContent = '⏳ Adding...';
      fetch('/api/youtube/add', {{
        method: 'POST',
        headers: {{'Content-Type':'application/json'}},
        body: JSON.stringify({{
          channel_id: document.getElementById('new_cid').value,
          name: document.getElementById('new_name').value,
          discord_channel: document.getElementById('new_dc').value,
          ping_role: document.getElementById('new_role').value || null,
          message: document.getElementById('new_msg').value
        }})
      }}).then(r=>r.json()).then(d=>{{
        if(d.ok) {{ status.style.color='#23a55a'; status.textContent='✅ '+d.msg; setTimeout(()=>location.reload(),1500); }}
        else     {{ status.style.color='#ed4245'; status.textContent='❌ '+d.msg; }}
      }});
    }}
    </script>
    '''
    return render('youtube', '📺 YouTube Alerts', 'Get notified when your favourite channels upload', body)

# YouTube API endpoints
@app.route('/api/youtube/save', methods=['POST'])
def api_youtube_save():
    gid = get_gid() or 'default'
    data = request.json
    cid  = data.get('channel_id')
    yt   = load('youtube.json')
    cfg  = yt.setdefault(gid, {}).setdefault('channels', {}).setdefault(cid, {})
    if data.get('discord_channel'): cfg['discord_channel'] = data['discord_channel']
    if data.get('ping_role'):       cfg['ping_role'] = data['ping_role']
    if data.get('message'):         cfg['message']   = data['message']
    save('youtube.json', yt)
    if hasattr(__builtins__, 'refresh_bot_cache'): refresh_bot_cache()
    return jsonify({'ok': True})

@app.route('/api/youtube/toggle', methods=['POST'])
def api_youtube_toggle():
    gid = get_gid() or 'default'
    data = request.json
    yt   = load('youtube.json')
    yt.setdefault(gid, {}).setdefault('channels', {}).setdefault(data['channel_id'], {})['enabled'] = data['enabled']
    save('youtube.json', yt)
    return jsonify({'ok': True})

@app.route('/api/youtube/remove', methods=['POST'])
def api_youtube_remove():
    gid = get_gid() or 'default'
    cid  = request.json.get('channel_id')
    yt   = load('youtube.json')
    yt.get(gid, {}).get('channels', {}).pop(cid, None)
    save('youtube.json', yt)
    return jsonify({'ok': True})

@app.route('/api/youtube/add', methods=['POST'])
def api_youtube_add():
    gid  = get_gid() or 'default'
    data = request.json
    cid  = data.get('channel_id', '').strip()
    dc   = data.get('discord_channel', '').strip()
    if not cid or not dc:
        return jsonify({'ok': False, 'msg': 'Channel ID and Discord channel are required!'})
    yt = load('youtube.json')
    yt.setdefault(gid, {}).setdefault('channels', {})[cid] = {
        'name':            data.get('name') or cid,
        'discord_channel': dc,
        'ping_role':       data.get('ping_role'),
        'message':         data.get('message', '🎬 **{author}** uploaded **{title}**!\n{url}'),
        'enabled':         True,
        'last_video_id':   None
    }
    save('youtube.json', yt)
    return jsonify({'ok': True, 'msg': f'Added! Bot will check for new videos every 10 min.'})

@app.route('/api/youtube/test', methods=['POST'])
def api_youtube_test():
    return jsonify({'ok': True, 'msg': 'Use /youtube test <channel_id> in Discord to test!'})

# ══════════════════════════════════════════════════════════
#  STORY MODE PAGE
# ══════════════════════════════════════════════════════════
@app.route('/story')
def story():
    gid = get_gid() or 'default'
    st_data = load('story.json').get(gid, {})
    
    body = f"""
    <div class="card">
      <div class="card-header"><h3>📖 Ongoing Story Session</h3></div>
      <div class="card-body">
        <p style="font-size:14px;color:#b5bac1;">Active Authors/Contributors recorded: <b style="color:#fff;">{len(st_data)} members</b></p>
        <p style="font-size:13px;color:#4e5058;margin-top:12px;">Full adventure configurations are generated directly via storytelling interactions inside discord channels.</p>
      </div>
    </div>
    """
    return render('story', '📖 Story Adventure Mode', 'Track server generated text simulations and interactive histories', body)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
