# BeamNG Info Config Generator

A GUI tool for generating and managing `info_*.json` config files for BeamNG.drive mods.
Designed for use with **RLS Career Overhaul** — cars require a valid info config to appear in dealer shops.

---

## Screenshots

![Main view](https://github.com/Holorigg/beamng-info-config-generator/releases/download/v1.0.3/1_clean.png)

![Editor with dealer card preview](https://github.com/Holorigg/beamng-info-config-generator/releases/download/v1.0.3/2_clean.png)

---

## Requirements

- Python 3.10+
- PySide6

```
pip install PySide6
```

---

## 🚀 Running

```
python main.py
```

To open directly with a mods folder:

```
python main.py --mods-path "C:/Users/you/AppData/Local/BeamNG/BeamNG.drive/current/mods"
```

The path is saved automatically after the first scan.

---

## 📖 Workflow

### 1. Scan your mods

Click **Browse** to select your BeamNG mods folder, then click **Scan**.
The tool supports both `.zip` mods and extracted mod folders.

The left panel shows all detected `.pc` configs grouped by mod, with status indicators:

| Status | Meaning |
|--------|---------|
| `[✓]` | Info config exists and all required fields are filled |
| `[!]` | Info config exists but has missing or empty required fields |
| `[✗]` | No info config file found |

Click the colored filter buttons in the panel header to show/hide configs by status.

### 2. Generate missing configs

Click **Generate all [✗]** to create info configs for every mod that is missing one.
Values are taken from the editor form on the right and auto-detected from the `.pc` file where possible.

### 3. Fix incomplete configs

Click **Fix all [!]** to fill missing fields in configs that already exist.
Existing values are preserved; only blank fields are filled in.

### 4. Edit a single config

Click any config in the left panel to open it in the editor.

- The **form** lets you set drivetrain, transmission, fuel type, body style, price range, stats, and description.
- The **Raw JSON** editor shows the full file with syntax highlighting — you can edit it directly.
- The **dealer card preview** at the bottom updates in real time as you type.
- **Save** (`Ctrl+S`) — write form values to disk.
- **Regenerate** — overwrite the config completely using the current form values.
- **Save JSON** — save whatever is in the raw JSON editor, bypassing the form.
- **Copy from...** — copy field values from another config in your collection.

### 5. Generate selected

Hold `Ctrl` or `Shift` to select multiple configs. The **Generate selected (N)** button creates or overwrites configs for the selection using the current form values.

### 6. Analyze 🔍

Click **Analyze** to get a report of every config that has issues preventing it from appearing in the dealer shop.

- **Critical** — the car will not appear (missing file, empty required fields, price is zero)
- **Warning** — the car may appear but with incomplete data (no description, stats not filled)

Use **Copy report** to copy the full list to clipboard.

### 7. Table view

Click **⊞** in the panel header to switch to a flat sortable table of all configs.
Click any column header to sort. Click a row to load that config in the editor.
Click **≡** to switch back to the tree.

### ⌨️ Keyboard shortcuts

| Key | Action |
|-----|--------|
| `Ctrl+S` | Save current config |
| `F5` | Rescan the mods folder |

---

## 📁 File naming convention

Info configs must follow this naming pattern and be placed in the same folder as the `.pc` file:

```
info_{config_name}.json
```

Example: `vehicles/myCar/sport_v8.pc` → `vehicles/myCar/info_sport_v8.json`

---

## ✅ Required fields

A config must contain all of the following to be considered valid:

- `Configuration` — internal name (filled automatically from the `.pc` filename)
- `Config Type` — `Factory`, `Custom`, or `Race`
- `Drivetrain` — `RWD`, `AWD`, or `FWD`
- `Transmission` — `Automatic`, `Manual`, `DCT`, or `CVT`
- `Fuel Type` — `Gasoline`, `Diesel`, `Electric`, or `Hybrid`
- `Value` — price in credits (must be greater than zero)
