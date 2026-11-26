"""Render the demo replies in a real omp session: in a terminal as HTML pages to screenshot, and in
Tern's native view as finished screenshots.

  python3 demo/shots.py            writes reply.html, without.html and vocabulary.html to demo/out/,
                                   and tern-reply.png and tern-vocabulary.png to screenshots/

Each reply in demo/*.md is placed in a session file as an assistant message and opened by omp with
only this extension loaded. For the terminal, omp runs inside a detached tmux session and the drawn
screen is converted to HTML: screenshot the <pre id="t"> element of each page with any browser. For
Tern, omp runs inside a headless Tern (`tern serve`), which shoots the window itself. Needs omp, tmux,
tern, and a JetBrains Mono Nerd Font in ~/Library/Fonts. No model is called.
"""
import html, json, os, pathlib, re, shlex, shutil, subprocess, time, uuid

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "demo/out"
# The omp on this shell's PATH: tmux starts a login shell, whose PATH may find a different one.
OMP = shlex.quote(shutil.which("omp") or "omp")
TERN = shutil.which("tern") or "/Applications/Tern.app/Contents/MacOS/tern"
FONT = "file://" + str(pathlib.Path.home() / "Library/Fonts/JetBrainsMonoNerdFont-")
A16=["#1d1f21","#e06c75","#98c379","#e5c07b","#61afef","#c678dd","#56b6c2","#d7dae0","#5c6370","#e06c75","#98c379","#e5c07b","#61afef","#c678dd","#56b6c2","#ffffff"]
def c256(n):
    if n<16: return A16[n]
    if n<232:
        n-=16; v=[0,95,135,175,215,255]; return "#%02x%02x%02x"%(v[n//36],v[n//6%6],v[n%6])
    g=8+(n-232)*10; return "#%02x%02x%02x"%(g,g,g)
BG,FG="#15171c","#d7dae0"
def convert(ansi):
    st=dict(fg=None,bg=None,b=False,i=False,u=False,r=False,d=False)
    out=[]
    for part in re.split(r'(\x1b\[[0-9;]*m)',ansi):
        m=re.fullmatch(r'\x1b\[([0-9;]*)m',part)
        if not m:
            if not part: continue
            fg,bg=st['fg'] or FG, st['bg'] or BG
            if st['r']: fg,bg=bg,fg
            css=f"color:{fg};"
            if bg!=BG: css+=f"background:{bg};"
            if st['b']: css+="font-weight:bold;"
            if st['i']: css+="font-style:italic;"
            if st['u']: css+="text-decoration:underline;"
            if st['d']: css+="opacity:.6;"
            out.append(f'<span style="{css}">{html.escape(part)}</span>'); continue
        codes=[int(x) if x else 0 for x in m.group(1).split(';')]; i=0
        while i<len(codes):
            c=codes[i]
            if c==0: st=dict(fg=None,bg=None,b=False,i=False,u=False,r=False,d=False)
            elif c==1: st['b']=True
            elif c==2: st['d']=True
            elif c==3: st['i']=True
            elif c==4: st['u']=True
            elif c==7: st['r']=True
            elif c==22: st['b']=False; st['d']=False
            elif c==23: st['i']=False
            elif c==24: st['u']=False
            elif c==27: st['r']=False
            elif 30<=c<=37: st['fg']=A16[c-30]
            elif 90<=c<=97: st['fg']=A16[c-82]
            elif c==39: st['fg']=None
            elif 40<=c<=47: st['bg']=A16[c-40]
            elif 100<=c<=107: st['bg']=A16[c-92]
            elif c==49: st['bg']=None
            elif c in (38,48):
                k='fg' if c==38 else 'bg'
                if codes[i+1]==2: st[k]="#%02x%02x%02x"%tuple(codes[i+2:i+5]); i+=4
                else: st[k]=c256(codes[i+2]); i+=2
            i+=1
    return "".join(out)


def session(name, prompt, reply):
    """An omp session file of the shot's own, holding one prompt and one scripted assistant reply.

    One file per shot: an omp killed after its shot appends its exit record a moment later, and in a
    shared file that record would land in the next shot's session and cut its transcript.
    """
    rows = [{"type": "session", "version": 3, "id": str(uuid.uuid4()), "timestamp": "2026-01-01T10:00:00.000Z", "cwd": str(OUT)}]
    parent = None
    for message in (
        {"role": "user", "content": [{"type": "text", "text": prompt}], "timestamp": 1},
        {"role": "assistant", "content": [{"type": "text", "text": reply}], "api": "anthropic-messages", "provider": "demo", "model": "demo",
         "usage": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0, "totalTokens": 0, "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0, "total": 0}},
         "stopReason": "stop", "timestamp": 2},
    ):
        row = {"type": "message", "id": uuid.uuid4().hex[:8], "parentId": parent, "timestamp": "2026-01-01T10:00:01.000Z", "message": message}
        rows.append(row)
        parent = row["id"]
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{name}.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return path


def agent_dir():
    """An omp agent folder of its own, with titanium and extension reply renderers on."""
    agent = OUT / "agent"
    agent.mkdir(parents=True, exist_ok=True)
    (agent / "config.yml").write_text("theme:\n  dark: titanium\nsetupVersion: 3\nextensionRenderers:\n  assistantText: true\n")
    return agent


def omp_command(path, extension=True):
    load = f"-e {ROOT / 'index.ts'}" if extension else ""
    return f"cd {OUT} && PI_CODING_AGENT_DIR={agent_dir()} COLORTERM=truecolor {OMP} --resume {path} --no-extensions {load} --no-skills --no-context-files --offline"


def shot(name, prompt, reply_file, extension=True, rows=60, cols=112):
    path = session(name, prompt, (ROOT / "demo" / reply_file).read_text())
    command = f"{omp_command(path, extension)}; sleep 60"
    tmux = "omp-emphasis-shot"
    subprocess.run(["tmux", "kill-session", "-t", tmux], capture_output=True)
    subprocess.run(["tmux", "new-session", "-d", "-s", tmux, "-x", str(cols), "-y", str(rows), command], check=True)
    time.sleep(8)
    raw = subprocess.run(["tmux", "capture-pane", "-t", tmux, "-p", "-e"], capture_output=True, text=True).stdout
    subprocess.run(["tmux", "kill-session", "-t", tmux], capture_output=True)
    lines = raw.split("\n")
    plain = [re.sub(r"\x1b\[[0-9;]*m", "", line) for line in lines]
    start = next(i for i, line in enumerate(plain) if prompt in line) - 1
    end = next(i for i, line in enumerate(plain) if line.strip().startswith("Warning:"))
    while not plain[end - 1].strip():
        end -= 1
    body = "\n".join(convert(line) for line in lines[start:end])
    (OUT / f"{name}.html").write_text(f"""<!doctype html><meta charset=utf-8><style>
@font-face{{font-family:T;src:url({FONT}Medium.ttf);font-weight:normal}}
@font-face{{font-family:T;src:url({FONT}ExtraBold.ttf);font-weight:bold}}
body{{margin:0;background:{BG}}} pre{{display:inline-block;margin:0;padding:22px 26px;font:15px/1.5 T;color:{FG};background:{BG}}}
</style><pre id=t>{body}</pre>""")
    print(OUT / f"{name}.html")


def tern_shot(name, prompt, reply_file, width=960, margin=24):
    """Shoot the reply in a headless Tern's native view, titanium dark, and write screenshots/<name>.png."""
    path = session(name, prompt, (ROOT / "demo" / reply_file).read_text())
    # Tern state of its own with the plugin linked, so the extension finds it and sends link pills.
    env = {**os.environ, "TERN_CONFIG_DIR": str(OUT / "tern")}
    subprocess.run([TERN, "plugin", "link", str(ROOT / "tern")], env=env, check=True, capture_output=True)
    sock = OUT / "tern.sock"
    serve = subprocess.Popen([TERN, "serve", "--control", str(sock), "--out", str(OUT / "tern-shots")], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def ctl(*args):
        reply = json.loads(subprocess.run([TERN, "ctl", "--control", str(sock), *args], capture_output=True, text=True, check=True).stdout)
        if not reply.get("ok"):
            raise RuntimeError(f"tern ctl {' '.join(args)}: {reply}")
        return reply

    try:
        time.sleep(3)
        ctl("resize", str(width), "1600")
        ctl("theme", "titanium")
        ctl("appearance", "dark")
        # ctl reads one quoted argument; the command holds no double quotes.
        ctl("type", f'"{omp_command(path)}"')
        ctl("key", "enter")
        time.sleep(10)
        # A headless Tern loads no plugins, so the pill sheet goes in by hand.
        ctl("css", "omp-emphasis", str(ROOT / "tern/pills.css"))
        time.sleep(1)
        taken = ctl("shot", name)
    finally:
        subprocess.run([TERN, "ctl", "--control", str(sock), "quit"], capture_output=True)
        serve.wait(timeout=10)
    # Crop to the prompt card and the reply below it, from the layout Tern writes beside the picture.
    layout = json.loads(pathlib.Path(taken["layout"]).read_text())
    scale = layout["viewport"]["deviceScaleFactor"]
    elements = layout["elements"]
    shown = lambda end: next(e for e in elements if e["path"].endswith(end) and e["rect"][2] > 0)
    # The prompt is the card holding Markdown; omp's logo above it is a card too.
    prompt_md = shown("div.sf.sf-card.nohead>div.sf-card-body>div.sf.sf-md")
    card_nth = ">".join(prompt_md["nth"].split(">")[:-2])
    prompt_card = next(e["rect"] for e in elements if e["nth"] == card_nth)
    reply = shown("div.sf.sf-col.gap-none>div.sf.sf-md")["rect"]
    left, top = reply[0] - margin, prompt_card[1] - margin
    right, bottom = prompt_card[0] + prompt_card[2] + margin, reply[1] + reply[3] + margin
    target = ROOT / "screenshots" / f"{name}.png"
    subprocess.run(["sips", "-c", str(round((bottom - top) * scale)), str(round((right - left) * scale)), "--cropOffset", str(round(top * scale)), str(round(left * scale)), taken["png"], "--out", str(target)], check=True, capture_output=True)
    print(target)


if __name__ == "__main__":
    deploy = "The staging deploy for checkout failed again. What happened?"
    shot("reply", deploy, "deploy-reply.md")
    shot("without", deploy, "deploy-reply.md", extension=False)
    shot("vocabulary", "Show me every pill.", "every-pill.md")
    tern_shot("tern-reply", deploy, "deploy-reply.md")
    tern_shot("tern-vocabulary", "Show me every pill.", "every-pill.md")
