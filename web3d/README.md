# Farmer Replica — Web 3D

A browser-based 3D adaptation in its own folder. The desktop game source remains
unchanged. Three.js renders the field; the UI follows the desktop arrangement
(resource overlay, floating code windows, Run/Stop, and research).

## Run locally on Windows

From the project root:

```powershell
py -m http.server 8000
```

Open <http://localhost:8000/web3d/> in a browser. Stop the server with
**Ctrl+C** in the terminal. The web app loads Three.js from jsDelivr, so the
browser needs an internet connection on first load.

## First gameplay slice

1. Wait until the grass shows **READY TO HARVEST**, then run `harvest()`.
   Repeat only when it is ready; harvesting early removes the crop without
   yielding Hay.
2. Collect 5 Hay and unlock **Loops**. Collect 20 more Hay for **Speed**, then
   30 more for **Expand**. Expand opens movement and grows the field to 1x3.
   Moving beyond a field edge wraps the drone to the opposite side of the field.
3. Collect 50 more Hay and unlock **Plant**. On a grassland tile, run
   `plant(Entities.Bush)`, wait until it is ready, then run `harvest()` to get 1 Wood.
   Repeat the planting and harvesting cycle until you have 20 Wood.
4. Unlock **Expand_2** for 20 Wood. It clears and expands the field to 3x3 and
   unlocks `for`, `range()`, and `get_world_size()`. The Guide's field-sweep
   example visits every tile in a safe zigzag and returns to `(0, 0)`.
   With **Plant**, **Loops**, **Operators**, and **Senses**, its bush-farming
   example plants, waits for, and harvests a bush at each tile in one pass.
5. Unlock **Carrots** for 50 Wood after **Plant**. Unlock **Operators** and
   **Senses** to use the carrot automation example in the in-game guide. It
   converts grassland tiles to soil, plants carrots, and harvests only when
   ready. Each carrot seed costs 512 Hay and 512 Wood, so make sure there are
   enough resources before planting.

## Current implementation

- 3D generated field and crops plus procedural low-poly drone, bush, grass, and
  field-tile assets in `drone-model.js`. The drone has four counter-rotating
  propellers, motor pods, camera, and landing skids; foliage uses faceted green
  clusters and pointed blades. Field tiles have a thin grass cap, layered brown
  earth, and embedded low-poly stones; tilling swaps the top for furrowed soil.
  The field is initially framed from above at a three-quarter angle; drag to pan
  the field and editor windows together without rotating the field, and scroll
  to zoom both.
- Transparent overlay header that keeps resource and game controls without a
  full-width top bar.
- Draggable editor windows with matching controls and behavior. Add editors
  with `+ EDITOR`, rename their titles inline, and confirm before closing.
  Windows can be dragged beyond the workspace edges; pan the view to bring an
  off-screen window back. Script text and editor titles are stored per profile
  in browser localStorage.
- Editor windows start at about 40 character columns by 10 visible lines and
  can be resized freely from their lower-right corner. Long lines scroll
  horizontally instead of resizing the window; additional lines scroll
  vertically. The current script line is highlighted during execution. Script
  errors open a dialog and mark the affected line with a red border. The
  separate output panel has been removed.
- Click a field tile to select it and show a white outline plus a cursor-following
  card with its coordinates, plant, growth progress, ground, and water level.
- Live drone movement while scripts run, with a raised hover height that keeps
  its low-poly body and landing gear clear of crop models. A piggy-bank drone
  with matching counter-rotating propellers circles the field; harvest-yield
  particles fly to it and it reacts with a small receiving animation. Harvest
  inventory and gameplay rules are unchanged.
- `do_a_flip()` is available from the start and performs a full drone flip. It
  takes one real-time second, independent of Speed upgrades, while game ticks
  and crop growth continue at the current speed.
- A draggable, resizable Guide window over the main farm view. Its navigable
  sections cover General Info, research info boxes, tool tips, other
  information, code snippets, and removed Wiki functions. Wiki material is
  summarized in Indonesian, source-linked, and labels features not implemented
  by the replica as reference-only.
- A full-screen research skill tree that replaces the farm view, with movable
  and zoomable nodes, shared branch connectors, hover-following descriptions,
  and a `FARM` button to return to the field. The tree keeps its zoom and pan
  while research resources change during a running script; unlock eligibility
  still follows each node's prerequisite data. Multi-level upgrades show their
  current level, maximum level, and next cost; reaching the cap displays `MAX`.
- The 3D render loop continues while scripts execute. The drone flies between
  tiles instead of teleporting, harvest actions animate the drone and show a
  short harvest effect, and crop models update their growth continuously without
rebuilding the field meshes. The Web 3D game's base speed is 2x (800 ticks per
second); Speed upgrades further accelerate tick-based actions, crop growth,
idle growth, and their visual action effects. Short consecutive operations
share a cumulative tick deadline so browser timer precision does not slow each
one independently. `do_a_flip()` remains a fixed one-second animation.
- Bushes use a shorter model to keep them from obscuring the drone and nearby
  tiles.
- Movement, sensor access, and action tick costs follow the game logic and cost
  data in the Python project. Moving beyond a field edge wraps the drone to the
  opposite side; the visual movement hides briefly at the edge instead of
  showing the drone travel outside the field.
  `Expand` unlocks movement;
  `Expand_2` unlocks `for`, `range()`, and `get_world_size()`.
- Offline login/registration with locally PBKDF2-hashed passwords and per-account
  progress saves in browser `localStorage`.
- The local account named `admin` receives the `developer` tag after
  authentication and can set Hay, Wood, Carrot, and Water counts from the
  `DEV RESOURCES` panel. This is a local development convenience, not secure
  server-side authorization.
- JavaScript implementation of the initial grass field, inventory, research
  costs/prerequisites, and a restricted script interpreter.
- Guide examples for basic `if`, comparison `if`, and sensor `if`; locked
  interpreter features report the research unlock needed to use them.
- Bush and carrot planting, tilling, harvesting, crop growth, and water-based
  growth acceleration. The field HUD shows the current tile's crop progress and
  water level.

This is an initial browser port, not full parity with every existing game
feature. The editor currently supports basic commands, `while`, `if/else`,
`for range`, variables after unlock, sensors, and the currently wired unlocks.
Only Bush and Carrot are implemented as plantable crops; other crop types,
advanced collections/custom functions, and tutorial flows still need porting.
Growth and planting values use the existing project data, which marks some crop
timing values as placeholders. All 3D models are generated placeholders rather
than copied commercial assets.
