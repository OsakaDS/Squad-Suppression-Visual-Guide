# Runbook: hosting and rebuilding

Operational commands for the Squad suppression toolkit. For what the software is, what
it found and how the extraction works, see **[README.md](README.md)**.

**Use this when you want to:** put the page on your network or the internet, restart the
server, or rebuild the page after Squad updates.

**Prerequisites:** Python 3.8+. `pip install pillow` for icon extraction. A copy of the
Squad Mod SDK for rebuilding, not needed just to host what is already built.

---

## Hosting the page

The site is **two static HTML files**, `index.html` (the field guide, 150 KB) and
`modders.html` (the data page, 1.3 MB), with everything inlined. No backend, no database.
Anything that can serve a file works.

### On your network

```bash
python3 serve.py
```

Prints both URLs, `http://localhost:8080` and the LAN one, currently
`http://192.168.1.59:8080`. Pass a port as the first argument to change it. `serve.py`
gzips on the fly (1332 KB → **777 KB** over the wire) and sets the UTF-8 charset that
`python3 -m http.server` omits.

If other machines can't reach it, check that a firewall isn't blocking the port (yours
is currently inactive), and note that an active VPN interface can shadow LAN routes.

### Keep it running

```bash
cp squad-suppression.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now squad-suppression
loginctl enable-linger osaka          # keeps it up while you are logged out
```

Check on it with `systemctl --user status squad-suppression`, logs with
`journalctl --user -u squad-suppression -f`. Stop with
`systemctl --user disable --now squad-suppression`.

### Docker

```bash
docker compose up -d      # nginx:alpine on :8080, gzip on, restart: unless-stopped
```

Uses `docker-compose.yml` and `nginx.conf`. Pulls the image on first run. Down with
`docker compose down`.

### On the public internet

Upload `docs/index.html` to any static host: **GitHub Pages, Netlify Drop, Cloudflare
Pages**. It is a single file; drag and drop works, and all three are free.

For a temporary public link straight off this machine, needing nothing installed:

```bash
ssh -R 80:localhost:8080 nokey@localhost.run
```

Prints a public URL that lives as long as the SSH session.

### Offline networks

The page inlines everything except the Google Fonts stylesheet. With no internet the type
falls back to the declared stacks; the page still works, it just looks different. Inline
the three fonts as base64 in `suppression.template.html` if you need it truly offline;
costs about 150 KB.

---

## Rebuilding

```bash
./build.sh
```

Runs the thirteen-step chain end to end in about a second and is byte-reproducible. The steps
and what each produces are tabulated in [README.md](README.md#reproducing-it). To run one
stage on its own, invoke that script directly; each writes its own JSON and the next
step picks it up.

**Edit `guide.template.html` and `suppression.template.html`, never the generated `.html`
files**, because `build_guide.py` and `build_page.py` overwrite them.

After a Squad update, rerun `./build.sh` and check the counts it prints; a jump or drop
in resolved weapons is the fastest signal that an asset format or a property name moved.

The vehicle sweep sits outside `build.sh` because it is the slow part and only moves when
the game does. Rerun it separately after an update:

```bash
python3 extract_vehicles.py && python3 report_vehicles.py && python3 build_vehicle_payload.py
```

### If a rebuild goes wrong

Nothing is destructive; every script rewrites its own outputs from the game assets, so
rerunning is always safe. To get back to a known-good page without rebuilding, keep a
copy of `docs/index.html`; it has no dependencies and will serve forever.

### Pointing at a different SDK install

Four files hold an absolute SDK path: `squad.py` (`CONTENT`, the one that matters),
`extract_all.py` (`ITEMS`), `dump_all.py` (`SI_DIR`) and `build_gui_data.py` (`SOLDIER`).
`squad-suppression.service` also hard-codes this directory.

---

## Data out

| File | Contents |
|---|---|
| `squad_all_weapons_suppression.csv` | all 521 weapons, power sampled at 1/2/3/4 m |
| `squad_vehicle_weapons.csv` | all 254 vehicle weapon systems, with class, profile and both models |
| `squad_materials.csv` | all 129 physical materials, armour value and damage absorbed |
| `all_materials.json` | the same, plus the ten heavy-calibre penetration curves |
| `vehicle_payload.json` | per-class figures and vehicle weapon art for the guide's second tab |
| `squad_rifle_suppression.csv` | the original ten-rifle sample |
| `all_profiles.json` | all 58 suppression profiles with raw curve keys |
| `all_weapons_raw.json` | every weapon asset before grouping, 904 rows |
| `docs/index.html` | the field guide, both tabs |
| `docs/modders.html` | the data page |
| `SUPPRESSION_LOGIC.md` | the decoded soldier-side logic |

## Gotchas

- **`grep` needs `-a`** on `.uasset` files. Without it grep treats them as binary and
  silently reports nothing, which reads exactly like "this string isn't in the assets".
- `Content/` is 246 GB. Never run a recursive grep over the whole tree; target a
  subdirectory.
- Squad's asset paths are case-inconsistent (`FC_SuppressionPower_RIfles` in a reference
  vs the object's `..._Rifles`). `squad.asset_path()` falls back to a case-insensitive
  directory lookup; keep that if you refactor it.
