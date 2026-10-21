const MAX_WORLD_SIZE = 10;
export const GAME_SPEED_MULTIPLIER = 2;
export const TICKS_PER_SECOND = 400 * GAME_SPEED_MULTIPLIER;
const FEATURE_RESEARCH = {
  movement: "Expand",
  while: "Loops",
  for_loop: "Expand_2",
  world_size: "Expand_2",
  planting: "Plant",
  till: "Carrots",
  carrots: "Carrots",
  senses: "Senses",
  watering: "Watering",
  timing: "Timing",
  costs: "Costs",
  operators: "Operators",
  variables: "Variables",
  lists: "Lists",
  dictionaries: "Dictionaries",
  utilities: "Utilities",
};
const GAME_FUNCTION_ARITIES = {
  harvest: [0, 0],
  clear: [0, 0],
  do_a_flip: [0, 0],
  move: [1, 1],
  plant: [1, 1],
  till: [0, 0],
  can_harvest: [0, 0],
  get_ground_type: [0, 0],
  get_entity_type: [0, 0],
  get_pos_x: [0, 0],
  get_pos_y: [0, 0],
  can_move: [1, 1],
  num_items: [1, 1],
  num_unlocked: [1, 1],
  get_world_size: [0, 0],
  get_water: [0, 0],
  use_item: [1, 2],
  get_time: [0, 0],
  get_tick_count: [0, 0],
  get_cost: [1, 2],
};

export class AccountError extends Error {}

export class Inventory {
  constructor(items = {}) {
    this.items = { ...items };
  }

  count(item) {
    return this.items[item] ?? 0;
  }

  add(item, amount = 1) {
    this.items[item] = this.count(item) + amount;
  }

  canAfford(cost = {}) {
    return Object.entries(cost).every(([item, amount]) => this.count(item) >= amount);
  }

  pay(cost = {}) {
    if (!this.canAfford(cost)) return false;
    for (const [item, amount] of Object.entries(cost)) {
      this.items[item] = this.count(item) - amount;
    }
    return true;
  }
}

class LoopSignal extends Error {
  constructor(kind) {
    super(kind);
    this.kind = kind;
  }
}

function attachScriptLine(error, line) {
  if (error && typeof error === "object" && Number.isInteger(line) && !Number.isInteger(error.line)) {
    error.line = line;
  }
}

function requireArity(name, args, minimum, maximum = minimum) {
  if (args.length >= minimum && args.length <= maximum) return;
  const expected = minimum === maximum
    ? `${minimum}`
    : maximum === Infinity
      ? `at least ${minimum}`
      : `${minimum}-${maximum}`;
  throw new Error(`${name}() expects ${expected} argument(s), got ${args.length}.`);
}

export class GameWorld {
  constructor(entityDefs, width = 1, height = 1) {
    this.defs = entityDefs;
    this.resize(width, height);
    for (const column of this.tiles) {
      for (const tile of column) this.regrow(tile);
    }
  }

  resize(width, height) {
    if (!Number.isInteger(width) || !Number.isInteger(height) ||
      width < 1 || height < 1 || width > MAX_WORLD_SIZE || height > MAX_WORLD_SIZE) {
      throw new Error(`Field size must be 1-${MAX_WORLD_SIZE}.`);
    }
    const old = this.tiles ?? [];
    const oldWidth = this.width ?? 0;
    const oldHeight = this.height ?? 0;
    this.tiles = Array.from({ length: width }, (_, x) =>
      Array.from({ length: height }, (_, y) => old[x]?.[y] ?? this.newTile()));
    this.width = width;
    this.height = height;
    for (let x = 0; x < width; x += 1) {
      for (let y = 0; y < height; y += 1) {
        if (x >= oldWidth || y >= oldHeight) this.regrow(this.tiles[x][y]);
      }
    }
  }

  newTile() {
    return { ground: "grassland", entity: null, age: 0, water: 0 };
  }

  wrap(x, y) {
    return [((x % this.width) + this.width) % this.width, ((y % this.height) + this.height) % this.height];
  }

  tile(x, y) {
    const [wrappedX, wrappedY] = this.wrap(x, y);
    return this.tiles[wrappedX][wrappedY];
  }

  advance(ticks, secondsPerTick) {
    if (ticks <= 0) return;
    const waterDecay = 0.99 ** secondsPerTick;
    const totalDecay = waterDecay ** ticks;
    for (const column of this.tiles) {
      for (const tile of column) {
        if (tile.entity) {
          if (tile.water <= 0) tile.age += ticks;
          else {
            const accumulatedWater = tile.water * (1 - totalDecay) / (1 - waterDecay);
            tile.age += ticks + 4 * accumulatedWater;
          }
        }
        tile.water *= totalDecay;
      }
    }
  }

  isMature(tile) {
    return tile.entity !== null && tile.age >= this.defs[tile.entity].grow_ticks;
  }

  clearTile(tile) {
    tile.entity = null;
    tile.age = 0;
    this.regrow(tile);
  }

  regrow(tile) {
    const grass = this.defs.grass;
    if (tile.ground === "grassland" && grass?.auto_regrow) {
      tile.entity = "grass";
      tile.age = 0;
    }
  }

  toggleGround(tile) {
    tile.ground = tile.ground === "grassland" ? "soil" : "grassland";
    tile.entity = null;
    tile.age = 0;
    this.regrow(tile);
  }

  clearFarm() {
    for (const column of this.tiles) {
      for (const tile of column) {
        tile.ground = "grassland";
        tile.entity = null;
        tile.age = 0;
        tile.water = 0;
        this.regrow(tile);
      }
    }
  }
}

export class Progression {
  constructor(inventory, tree, data = {}) {
    this.inventory = inventory;
    this.tree = Object.fromEntries(Object.entries(tree).filter(([name]) => !name.startsWith("_")));
    this.unlocked = new Set(data.unlocked ?? []);
    this.upgradeLevels = { ...(data.upgrade_levels ?? {}) };
  }

  status(name) {
    const node = this.tree[name];
    if (!node) return "unknown";
    const levels = node.levels;
    if (levels && (this.upgradeLevels[name] ?? 0) >= levels.length) return "unlocked";
    if (!levels && this.unlocked.has(name)) return "unlocked";
    if (!(node.prerequisites ?? []).every((required) => this.unlocked.has(required))) return "locked";
    return "available";
  }

  currentCost(name) {
    const node = this.tree[name];
    if (!node) return null;
    if (node.levels) return node.levels[this.upgradeLevels[name] ?? 0]?.cost ?? null;
    return node.cost ?? null;
  }

  affordable(name) {
    const cost = this.currentCost(name);
    return cost !== null && this.inventory.canAfford(cost);
  }

  unlock(name) {
    if (this.status(name) !== "available" || !this.affordable(name)) return false;
    const node = this.tree[name];
    if (!this.inventory.pay(this.currentCost(name))) return false;
    this.unlocked.add(name);
    if (node.levels) this.upgradeLevels[name] = (this.upgradeLevels[name] ?? 0) + 1;
    return true;
  }

  features() {
    return new Set([...this.unlocked].flatMap((name) => this.tree[name]?.features ?? []));
  }

  numUnlocked(name) {
    if (this.tree[name]) {
      return this.tree[name].levels
        ? this.upgradeLevels[name] ?? 0
        : Number(this.unlocked.has(name));
    }
    const features = this.features();
    const entityFeatures = {
      grass: true,
      bush: features.has("planting"),
      carrot: features.has("carrots"),
      tree: features.has("trees"),
      pumpkin: features.has("pumpkins"),
      cactus: features.has("cactus"),
      sunflower: features.has("sunflowers"),
    };
    if (Object.hasOwn(entityFeatures, name)) return Number(entityFeatures[name]);
    if (name === "grassland" || name === "soil" || name === "hay") return 1;
    const itemFeatures = {
      wood: "planting",
      carrot: "carrots",
      pumpkin: "pumpkins",
      cactus: "cactus",
      power: "sunflowers",
      water: "watering",
      fertilizer: "fertilizer",
      weird_substance: "mazes",
      bone: "dinosaurs",
      gold: "mazes",
    };
    return Number(features.has(itemFeatures[name]));
  }

  speedMultiplier() {
    const levels = this.tree.Speed?.levels ?? [];
    const count = this.upgradeLevels.Speed ?? 0;
    return levels.slice(0, count).reduce(
      (multiplier, level) => multiplier * (level.effects?.speed_multiplier_per_level ?? 1),
      1,
    );
  }

  grassYieldMultiplier() {
    const levels = this.tree.Grass?.levels ?? [];
    const level = this.upgradeLevels.Grass ?? 0;
    return levels[level - 1]?.effects?.grass_yield_multiplier ?? 1;
  }

  wateringTanksPerTenSeconds() {
    const levels = this.tree.Watering?.levels ?? [];
    const level = this.upgradeLevels.Watering ?? 0;
    return levels[level - 1]?.effects?.water_tanks_per_10_seconds ?? 0;
  }
}

export class GameSession {
  constructor(entityDefs, costs, techTree, onChange = () => {}, saveKey) {
    this.entities = entityDefs;
    this.costs = costs;
    this.onChange = onChange;
    this.saveKey = saveKey ?? "farmer-replica-web-save";
    this.controller = null;
    this.tickCount = 0;
    this.log = [];
    this.harvestEvent = null;
    const saved = this.load();
    this.inventory = new Inventory(saved?.inventory);
    this.world = new GameWorld(entityDefs, saved?.world?.width ?? 1, saved?.world?.height ?? 1);
    if (saved?.world?.tiles) this.world.tiles = saved.world.tiles;
    this.drone = { x: saved?.drone?.x ?? 0, y: saved?.drone?.y ?? 0 };
    [this.drone.x, this.drone.y] = this.world.wrap(this.drone.x, this.drone.y);
    this.tickCount = saved?.clock_tick_count ?? 0;
    this.code = saved?.script ?? "harvest()";
    this.waterTimeSeconds = saved?.drone?.water_time_seconds ?? 0;
    this.executionStartTick = this.tickCount;
    this.tickDeadline = null;
    this.lastTickYield = 0;
    this.progression = new Progression(this.inventory, techTree, saved ?? {});
  }

  get running() {
    return this.controller !== null;
  }

  get tile() {
    return this.world.tile(this.drone.x, this.drone.y);
  }

  async advanceIdle(ticks, signal) {
    if (ticks < 1 || this.running) return;
    this.advanceTicks(ticks);
    this.notify();
    if (signal?.aborted) return;
  }

  advanceTicks(ticks) {
    const secondsPerTick = 1 / (TICKS_PER_SECOND * this.progression.speedMultiplier());
    this.tickCount += ticks;
    this.world.advance(ticks, secondsPerTick);
    const tanksPerTenSeconds = this.progression.wateringTanksPerTenSeconds();
    if (tanksPerTenSeconds > 0) {
      this.waterTimeSeconds += ticks * secondsPerTick;
      const tanksDue = Math.floor((this.waterTimeSeconds + 1e-12) / 10);
      if (tanksDue > 0) {
        this.waterTimeSeconds = Math.max(0, this.waterTimeSeconds - tanksDue * 10);
        this.inventory.add("water", tanksDue * tanksPerTenSeconds);
      }
    }
  }

  resetTickScheduler() {
    this.tickDeadline = performance.now();
    this.lastTickYield = this.tickDeadline;
  }

  async waitTicks(ticks, signal) {
    if (this.tickDeadline === null) this.resetTickScheduler();
    let remaining = ticks;
    while (remaining > 0) {
      if (signal.aborted) throw new DOMException("Execution stopped.", "AbortError");
      const speedMultiplier = this.progression.speedMultiplier();
      const batch = Math.min(Math.ceil(16 * speedMultiplier), remaining);
      this.advanceTicks(batch);
      remaining -= batch;
      this.tickDeadline += batch / (TICKS_PER_SECOND * speedMultiplier) * 1000;
      this.notify();

      const now = performance.now();
      const delay = this.tickDeadline - now;
      if (delay > 0 || now - this.lastTickYield >= 8) {
        await new Promise((resolve) => setTimeout(resolve, Math.max(0, delay)));
        this.lastTickYield = performance.now();
      }
    }
  }

  async perform(name, args, signal) {
    const [dx, dy] = {
      north: [0, 1], east: [1, 0], south: [0, -1], west: [-1, 0],
    }[args[0]] ?? [];
    let success = true;
    let value = null;
    let costName = name;
    let movementFrom = null;
    let fixedDurationSeconds = null;

    switch (name) {
      case "do_a_flip":
        fixedDurationSeconds = 1;
        break;
      case "harvest": {
        this.harvestEvent = null;
        const tile = this.tile;
        if (!tile.entity) {
          success = false;
          value = false;
          break;
        }
        const entity = tile.entity;
        const mature = this.world.isMature(tile);
        const yields = {};
        if (mature) {
          for (const [item, count] of Object.entries(this.entities[entity].yield ?? {})) {
            const amount = entity === "grass" && item === "hay"
              ? count * this.progression.grassYieldMultiplier()
              : count;
            this.inventory.add(item, amount);
            yields[item] = amount;
          }
        }
        this.harvestEvent = { entity, mature, yields };
        this.world.clearTile(tile);
        value = true;
        break;
      }
      case "move":
        if (!Number.isInteger(dx) || dx === undefined) {
          success = false;
          value = false;
          break;
        }
        movementFrom = { x: this.drone.x, y: this.drone.y };
        const nextX = this.drone.x + dx;
        const nextY = this.drone.y + dy;
        [this.drone.x, this.drone.y] = this.world.wrap(nextX, nextY);
        value = true;
        break;
      case "till":
        this.world.toggleGround(this.tile);
        break;
      case "clear":
        this.world.clearFarm();
        this.drone.x = 0;
        this.drone.y = 0;
        break;
      case "plant": {
        const entity = args[0];
        const definition = this.entities[entity];
        const tile = this.tile;
        const replaceableGrass = tile.entity === "grass" && this.entities.grass.auto_regrow;
        if (
          !definition
          || (tile.entity && !replaceableGrass)
          || tile.ground !== definition.requires_ground
          || !this.inventory.pay(definition.cost ?? {})
        ) {
          success = false;
          value = false;
          break;
        }
        tile.entity = entity;
        tile.age = 0;
        value = true;
        break;
      }
      case "use_item":
        if (
          args[0] !== "water"
          || !Number.isInteger(args[1] ?? 1)
          || (args[1] ?? 1) < 1
        ) {
          success = false;
          value = false;
          break;
        }
        {
          const requested = args[1] ?? 1;
          const tanksUsed = Math.min(
            requested,
            this.inventory.count("water"),
            Math.ceil(Math.max(0, 1 - this.tile.water) / 0.25),
          );
          if (!tanksUsed || !this.inventory.pay({ water: tanksUsed })) {
            success = false;
            value = false;
            break;
          }
          this.tile.water = Math.min(1, this.tile.water + 0.25 * tanksUsed);
          value = true;
        }
        break;
      case "can_harvest":
        costName = "can_harvest";
        value = this.world.isMature(this.tile);
        break;
      case "get_entity_type":
        costName = "get_entity_type";
        value = this.tile.entity;
        break;
      case "get_ground_type":
        costName = "get_ground_type";
        value = this.tile.ground;
        break;
      case "get_pos_x":
        costName = "get_pos_x";
        value = this.drone.x;
        break;
      case "get_pos_y":
        costName = "get_pos_y";
        value = this.drone.y;
        break;
      case "can_move":
        costName = "can_move";
        value = ["north", "east", "south", "west"].includes(args[0]);
        break;
      case "get_world_size":
        costName = "get_world_size";
        value = Math.max(this.world.width, this.world.height);
        break;
      case "get_water":
        costName = "get_water";
        value = this.tile.water;
        break;
      case "num_items":
        costName = "num_items";
        value = this.inventory.count(args[0]);
        break;
      case "num_unlocked":
        costName = "num_unlocked";
        value = this.progression.numUnlocked(args[0]);
        break;
      case "get_time":
        costName = "get_time";
        value = this.tickCount / TICKS_PER_SECOND;
        break;
      case "get_tick_count":
        costName = "get_tick_count";
        value = this.tickCount - this.executionStartTick;
        break;
      case "get_cost": {
        costName = "get_cost";
        const target = args[0];
        if (this.entities[target]) value = { ...(this.entities[target].cost ?? {}) };
        else {
          const unlock = this.progression.tree[target];
          if (!unlock) throw new Error(`get_cost does not recognize '${target}'.`);
          const level = args[1] ?? (this.progression.upgradeLevels[target] ?? 0);
          value = unlock.levels
            ? { ...(unlock.levels[level]?.cost ?? {}) }
            : level === 0 ? { ...(unlock.cost ?? {}) } : null;
        }
        break;
      }
      default:
        throw new Error(`Unknown game function: ${name}`);
    }

    const actionCost = this.costs.actions[costName];
    const ticks = fixedDurationSeconds !== null
      ? Math.round(TICKS_PER_SECOND * this.progression.speedMultiplier() * fixedDurationSeconds)
      : actionCost
        ? (success ? actionCost.success : actionCost.fail)
        : this.costs.sensors[costName] ?? this.costs.builtins[costName] ?? 0;
    this.log.push({
      tick: this.tickCount,
      name,
      args,
      success,
      ...(movementFrom ? { from: movementFrom, to: { ...this.drone } } : {}),
    });
    this.notify();
    if (ticks) await this.waitTicks(ticks, signal);
    return value;
  }

  unlock(name) {
    const unlocked = this.progression.unlock(name);
    if (unlocked && (name === "Expand" || name.startsWith("Expand_"))) {
      const definition = this.progression.tree[name];
      const level = name === "Expand" ? 1 : this.progression.upgradeLevels[name];
      const effects = definition.levels?.[level - 1]?.effects;
      if (effects?.width && effects?.height) {
        this.world.resize(effects.width, effects.height);
        this.world.clearFarm();
        [this.drone.x, this.drone.y] = this.world.wrap(this.drone.x, this.drone.y);
      }
    }
    this.notify();
    return unlocked;
  }

  notify() {
    this.onChange();
  }

  serialize(script = this.code) {
    return {
      version: 1,
      inventory: this.inventory.items,
      unlocked: [...this.progression.unlocked],
      upgrade_levels: this.progression.upgradeLevels,
      world: {
        width: this.world.width,
        height: this.world.height,
        tiles: this.world.tiles,
      },
      drone: {
        ...this.drone,
        water_time_seconds: this.waterTimeSeconds,
      },
      clock_tick_count: this.tickCount,
      script,
    };
  }

  save(script = this.code) {
    this.code = script;
    localStorage.setItem(this.saveKey, JSON.stringify(this.serialize(script)));
  }

  load() {
    try {
      const serialized = localStorage.getItem(this.saveKey);
      return serialized ? JSON.parse(serialized) : null;
    } catch (error) {
      console.error("Could not read the local game save.", error);
      return null;
    }
  }
}

class ExpressionParser {
  constructor(source, interpreter, variables, signal) {
    this.tokens = source.match(
      /\s*(\*\*|==|!=|<=|>=|\/\/|[A-Za-z_]\w*|\d+(?:\.\d+)?|[().+\-*/%<>=,:])/g,
    )?.map((token) => token.trim()).filter(Boolean) ?? [];
    this.index = 0;
    this.interpreter = interpreter;
    this.variables = variables;
    this.signal = signal;
  }

  peek() {
    return this.tokens[this.index];
  }

  take(expected) {
    const token = this.peek();
    if (expected && token !== expected) {
      throw new Error(`Expected '${expected}' in expression.`);
    }
    this.index += 1;
    return token;
  }

  async parse(minPrecedence = 0, evaluate = true) {
    let left = await this.prefix(evaluate);
    const precedence = {
      or: 1,
      and: 2,
      "==": 3, "!=": 3, "<": 3, "<=": 3, ">": 3, ">=": 3, in: 3, "not in": 3,
      "+": 4, "-": 4,
      "*": 5, "/": 5, "//": 5, "%": 5,
      "**": 6,
    };
    while (true) {
      let operator = this.peek();
      if (operator === "not" && this.tokens[this.index + 1] === "in") operator = "not in";
      const level = precedence[operator] ?? -1;
      if (level < minPrecedence) break;
      this.index += operator === "not in" ? 2 : 1;
      if (operator === "and" && !left) {
        if (evaluate) await this.interpreter.chargeOperator(operator, this.signal);
        await this.parse(level + 1, false);
        left = evaluate ? false : undefined;
        continue;
      }
      if (operator === "or" && left) {
        if (evaluate) await this.interpreter.chargeOperator(operator, this.signal);
        await this.parse(level + 1, false);
        left = evaluate ? true : undefined;
        continue;
      }
      const right = await this.parse(level + (operator === "**" ? 0 : 1), evaluate);
      if (!evaluate) {
        left = undefined;
        continue;
      }
      await this.interpreter.chargeOperator(operator, this.signal);
      left = this.apply(operator, left, right);
    }
    return left;
  }

  async prefix(evaluate) {
    const token = this.take();
    if (token === "(") {
      const value = await this.parse(0, evaluate);
      this.take(")");
      return value;
    }
    if (token === "not") {
      this.interpreter.validateOperator("not");
      const value = await this.parse(6, evaluate);
      return evaluate ? !value : undefined;
    }
    if (token === "-") {
      this.interpreter.validateOperator("-");
      const value = await this.parse(6, evaluate);
      return evaluate ? -value : undefined;
    }
    if (token === "+") {
      this.interpreter.validateOperator("+");
      const value = await this.parse(6, evaluate);
      return evaluate ? +value : undefined;
    }
    if (token === undefined) throw new Error("Unexpected end of expression.");
    if (/^\d/.test(token)) return Number(token);
    if (token === "True") return true;
    if (token === "False") return false;
    if (token === "None") return null;

    if (/^[A-Za-z_]\w*$/.test(token)) {
      if (this.peek() !== "(") {
        let value;
        if (Object.hasOwn(this.variables, token)) value = this.variables[token];
        else if (token in this.interpreter.constants) value = this.interpreter.constants[token];
        else throw new Error(`Unknown name: ${token}`);
        while (this.peek() === ".") {
          this.take(".");
          const member = this.take();
          if (value === null || typeof value !== "object" || !Object.hasOwn(value, member)) {
            throw new Error(`Unknown constant: ${token}.${member}`);
          }
          value = value[member];
        }
        return value;
      }
      this.take("(");
      const args = [];
      while (this.peek() !== ")") {
        args.push(await this.parse(0, evaluate));
        if (this.peek() !== ",") break;
        this.take(",");
      }
      this.take(")");
      return evaluate ? this.interpreter.call(token, args, this.signal) : undefined;
    }
    throw new Error(`Unsupported expression token: ${token}`);
  }

  apply(operator, left, right) {
    switch (operator) {
      case "or": return Boolean(left || right);
      case "and": return Boolean(left && right);
      case "==": return left === right;
      case "!=": return left !== right;
      case "<": return left < right;
      case "<=": return left <= right;
      case ">": return left > right;
      case ">=": return left >= right;
      case "in": return Array.isArray(right) ? right.includes(left) : String(right).includes(String(left));
      case "not in": return Array.isArray(right) ? !right.includes(left) : !String(right).includes(String(left));
      case "+": return left + right;
      case "-": return left - right;
      case "*": return left * right;
      case "/": return left / right;
      case "//": return Math.floor(left / right);
      case "%": return left % right;
      case "**": return left ** right;
      default: throw new Error(`Unsupported operator: ${operator}`);
    }
  }
}

export class GameInterpreter {
  constructor(session) {
    this.session = session;
    this.features = session.progression.features();
    this.constants = {
      Grounds: { Grassland: "grassland", Soil: "soil" },
    };
    if (this.features.has("movement")) {
      Object.assign(this.constants, {
        North: "north", East: "east", South: "south", West: "west",
      });
    }
    if (this.features.has("senses")) {
      this.constants.Items = {
        Hay: "hay", Wood: "wood", Carrot: "carrot", Pumpkin: "pumpkin",
        Cactus: "cactus", Gold: "gold", Power: "power", Water: "water",
        Fertilizer: "fertilizer", Weird_Substance: "weird_substance", Bone: "bone",
      };
    } else if (this.features.has("watering")) {
      this.constants.Items = { Water: "water" };
    }
    if (this.features.has("senses") || this.features.has("planting")) {
      this.constants.Entities = {
        Grass: "grass",
        ...(this.features.has("planting") ? { Bush: "bush" } : {}),
        ...(this.features.has("carrots") ? { Carrot: "carrot" } : {}),
      };
    }
    this.statementCount = 0;
    this.maxStatements = 10000;
  }

  async run(source, signal, onStep = () => {}) {
    const lines = source.split(/\r?\n/).map((text, index) => {
      const clean = text.replace(/#.*$/, "");
      return {
        text: clean.trim(),
        indent: clean.match(/^\s*/)[0].length,
        line: index + 1,
      };
    }).filter((line) => line.text);
    let nodes;
    try {
      nodes = this.parseBlock(lines, 0, lines[0]?.indent ?? 0).nodes;
    } catch (error) {
      const mentionedLine = error.message.match(/line (\d+)/i);
      const unsupportedFor = /for loops and range\(\)/i.test(error.message)
        ? lines.find((line) => line.text.startsWith("for "))
        : null;
      attachScriptLine(error, mentionedLine ? Number(mentionedLine[1]) : unsupportedFor?.line);
      throw error;
    }
    try {
      await this.execute(nodes, {}, signal, onStep);
    } catch (error) {
      if (error instanceof LoopSignal) {
        const invalidLoop = new Error(`${error.kind} can only be used inside a loop.`);
        attachScriptLine(invalidLoop, error.line);
        throw invalidLoop;
      }
      throw error;
    }
  }

  parseBlock(lines, start, indent) {
    const nodes = [];
    let index = start;
    while (index < lines.length) {
      const line = lines[index];
      if (line.indent < indent) break;
      if (line.indent > indent) throw new Error(`Unexpected indent on line ${line.line}.`);
      let match;
      if ((match = line.text.match(/^(while|if)\s+(.+):$/))) {
        const body = this.parseBlock(lines, index + 1, this.nextIndent(lines, index, indent));
        index = body.index;
        let otherwise = [];
        if (match[1] === "if" && lines[index]?.indent === indent && lines[index].text === "else:") {
          const branch = this.parseBlock(lines, index + 1, this.nextIndent(lines, index, indent));
          otherwise = branch.nodes;
          index = branch.index;
        }
        nodes.push({ type: match[1], expression: match[2], body: body.nodes, otherwise, line: line.line });
        continue;
      }
      if ((match = line.text.match(/^for\s+([A-Za-z_]\w*)\s+in\s+(range\(.*\)):$/))) {
        this.requireFeature("for_loop", "for loops and range()");
        const body = this.parseBlock(lines, index + 1, this.nextIndent(lines, index, indent));
        nodes.push({
          type: "for", name: match[1], expression: match[2],
          body: body.nodes, line: line.line,
        });
        index = body.index;
        continue;
      }
      if (/^(while|for)\b/.test(line.text)) {
        throw new Error(`Unsupported or locked loop on line ${line.line}.`);
      }
      const assignment = line.text.match(/^([A-Za-z_]\w*)\s*=\s*(.+)$/);
      nodes.push(assignment
        ? { type: "assign", name: assignment[1], expression: assignment[2], line: line.line }
        : ["break", "continue"].includes(line.text)
          ? { type: line.text, line: line.line }
          : { type: "expression", expression: line.text, line: line.line });
      index += 1;
    }
    return { nodes, index };
  }

  nextIndent(lines, index, current) {
    const next = lines[index + 1];
    if (!next || next.indent <= current) {
      throw new Error(`Expected an indented block after line ${lines[index].line}.`);
    }
    return next.indent;
  }

  async execute(nodes, variables, signal, onStep) {
    for (const node of nodes) {
      if (signal.aborted) throw new DOMException("Execution stopped.", "AbortError");
      this.statementCount += 1;
      if (this.statementCount > this.maxStatements) {
        const limitError = new Error("Execution step limit reached.");
        attachScriptLine(limitError, node.line);
        throw limitError;
      }
      onStep(node.line);
      try {
        if (node.type === "assign") {
          this.requireFeature("variables", "Variable assignments");
          variables[node.name] = await this.expression(node.expression, variables, signal);
        } else if (node.type === "expression") {
          await this.expression(node.expression, variables, signal);
        } else if (node.type === "if") {
          if (!this.features.has("operators") && /[<>=!]| and | or /.test(node.expression)) {
            this.requireFeature("operators", "Comparisons and boolean operators");
          }
          await this.session.waitTicks(this.session.costs.statements.if ?? 1, signal);
          const condition = await this.expression(node.expression, variables, signal);
          await this.execute(condition ? node.body : node.otherwise, variables, signal, onStep);
        } else if (node.type === "while") {
          this.requireFeature("while", "while loops");
          while (true) {
            await this.session.waitTicks(this.session.costs.statements.while ?? 1, signal);
            if (!await this.expression(node.expression, variables, signal)) break;
            try {
              await this.execute(node.body, variables, signal, onStep);
            } catch (error) {
              if (!(error instanceof LoopSignal)) throw error;
              if (error.kind === "break") break;
            }
          }
        } else if (node.type === "for") {
          const values = await this.expression(node.expression, variables, signal);
          if (!Array.isArray(values)) throw new Error("for loops require a supported range().");
          for (const value of values) {
            await this.session.waitTicks(this.session.costs.statements.for ?? 1, signal);
            variables[node.name] = value;
            try {
              await this.execute(node.body, variables, signal, onStep);
            } catch (error) {
              if (!(error instanceof LoopSignal)) throw error;
              if (error.kind === "break") break;
            }
          }
        } else if (node.type === "break" || node.type === "continue") {
          const loopSignal = new LoopSignal(node.type);
          attachScriptLine(loopSignal, node.line);
          throw loopSignal;
        }
      } catch (error) {
        attachScriptLine(error, node.line);
        throw error;
      }
    }
  }

  async expression(source, variables, signal) {
    const parser = new ExpressionParser(source, this, variables, signal);
    const result = await parser.parse();
    if (parser.index !== parser.tokens.length) {
      throw new Error(`Unexpected token '${parser.peek()}' in expression.`);
    }
    return result;
  }

  async call(name, args, signal) {
    const available = new Set(["harvest", "clear", "do_a_flip"]);
    if (this.features.has("movement")) available.add("move");
    if (this.features.has("planting")) available.add("plant");
    if (this.features.has("till")) available.add("till");
    if (this.features.has("senses")) {
      ["can_harvest", "get_ground_type", "get_entity_type", "get_pos_x", "get_pos_y",
        "can_move", "num_items", "num_unlocked"].forEach((item) => available.add(item));
    }
    if (this.features.has("world_size")) available.add("get_world_size");
    if (this.features.has("watering")) {
      available.add("get_water");
      available.add("use_item");
    }
    if (this.features.has("timing")) {
      available.add("get_time");
      available.add("get_tick_count");
    }
    if (this.features.has("costs")) available.add("get_cost");
    if (available.has(name)) {
      const [minimum, maximum] = GAME_FUNCTION_ARITIES[name] ?? [];
      requireArity(name, args, minimum, maximum);
      if (name === "plant") {
        const plantableEntities = new Set();
        if (this.features.has("planting")) plantableEntities.add("bush");
        if (this.features.has("carrots")) plantableEntities.add("carrot");
        if (!plantableEntities.has(args[0])) {
          throw new Error(`plant() does not support entity '${args[0]}'.`);
        }
      }
      if (name === "use_item" && args[0] !== "water") {
        throw new Error(`use_item() has not been unlocked for item '${args[0]}'.`);
      }
      return this.session.perform(name, args, signal);
    }
    if (name === "range" && this.features.has("for_loop")) {
      if (
        args.length < 1
        || args.length > 3
        || args.some((value) => !Number.isInteger(value))
      ) {
        throw new Error("range() requires one to three integer arguments.");
      }
      const [start, stop, step] = args.length === 1
        ? [0, args[0], 1]
        : args.length === 2 ? [args[0], args[1], 1] : args;
      if (step === 0) throw new Error("range() step cannot be zero.");
      const values = [];
      for (let value = start; step > 0 ? value < stop : value > stop; value += step) {
        if (values.length >= 10000) throw new Error("range() is limited to 10000 values.");
        values.push(value);
      }
      const ticks = this.session.costs.builtins.range ?? 0;
      if (ticks) await this.session.waitTicks(ticks, signal);
      return values;
    }
    if (["min", "max", "abs"].includes(name) && this.features.has("utilities")) {
      requireArity(name, args, 1, name === "abs" ? 1 : Infinity);
      if (name === "abs") return Math.abs(args[0]);
      return Math[name](...args);
    }
    const requiredFeature = {
      move: "movement",
      plant: args[0] === "carrot" ? "carrots" : "planting",
      till: "till",
      can_harvest: "senses",
      can_move: "senses",
      get_entity_type: "senses",
      get_ground_type: "senses",
      get_pos_x: "senses",
      get_pos_y: "senses",
      num_items: "senses",
      num_unlocked: "senses",
      get_world_size: "world_size",
      get_water: "watering",
      use_item: "watering",
      get_time: "timing",
      get_tick_count: "timing",
      get_cost: "costs",
      range: "for_loop",
      min: "utilities",
      max: "utilities",
      abs: "utilities",
    }[name];
    if (requiredFeature) {
      this.requireFeature(requiredFeature, `${name}()`);
    }
    throw new Error(`Unknown or locked game function: ${name}().`);
  }

  requireFeature(feature, capability) {
    if (this.features.has(feature)) return;
    const research = FEATURE_RESEARCH[feature];
    const detail = research ? ` Unlock "${research}" in RESEARCH first.` : "";
    throw new Error(`You need ${capability}.${detail}`);
  }

  async chargeOperator(operator, signal) {
    this.validateOperator(operator);
    const ticks = this.session.costs.operators[operator] ?? 0;
    if (ticks) await this.session.waitTicks(ticks, signal);
  }

  validateOperator(operator) {
    this.requireFeature("operators", "Operators");
    if (operator === "in" || operator === "not in") {
      if (!this.features.has("lists") && !this.features.has("dictionaries")) {
        throw new Error("Lists or Dictionaries have not been unlocked.");
      }
    } else if (!Object.hasOwn(this.session.costs.operators, operator)) {
      throw new Error(`No operation cost is configured for '${operator}'.`);
    }
  }
}
