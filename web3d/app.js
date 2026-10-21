import * as THREE from "three";
import {
  GAME_SPEED_MULTIPLIER,
  GameInterpreter,
  GameSession,
  TICKS_PER_SECOND,
} from "./game.js";
import {
  createLowPolyBush,
  createLowPolyDrone,
  createLowPolyFieldTile,
  createLowPolyGrass,
  createLowPolyPigDrone,
} from "./drone-model.js";
import {
  CODE_SNIPPETS,
  GENERAL_INFO,
  GUIDE_SECTIONS,
  OTHER_INFORMATION,
  REMOVED_ITEMS,
  TOOL_TIPS,
  WIKI_SOURCE,
} from "./guide-data.js";

const RESOURCE_NAMES = ["hay", "wood", "carrot", "water"];
const RESEARCH_NODE_SIZE = { width: 112, height: 78 };
const DRONE_HOVER_HEIGHT = 1.2;
const PIG_DRONE_HOVER_HEIGHT = 1.9;
const PIG_DRONE_ORBIT_SPEED = 0.34;
const RESEARCH_LAYOUT = {
  margin: 80,
  horizontalGap: 72,
  rootGap: 120,
  verticalGap: 92,
};
let researchCanvasSize = { width: 1600, height: 1200 };
const COLORS = {
  crop: { grass: "#b7d879", bush: "#53894b", tree: "#526e3f", carrot: "#d78745" },
};

const $ = (selector) => document.querySelector(selector);
const elements = {
  canvas: $("#world-canvas"),
  editorLayer: $("#editor-layer"),
  resources: $("#resources"),
  tick: $("#tick-count"),
  fieldSize: $("#field-size"),
  fieldCaption: $("#field-caption"),
  cropStatus: $("#crop-status"),
  fieldTooltip: $("#field-tooltip"),
  editorPanel: $("#editor-panel"),
  code: $("#editor-panel [data-code-input]"),
  lineNumbers: $("#editor-panel [data-line-numbers]"),
  action: $("#editor-panel [data-action-status]"),
  closeEditorDialog: $("#close-editor-dialog"),
  closeEditorMessage: $("#close-editor-message"),
  closeEditorConfirm: $("#close-editor-confirm"),
  closeEditorCancel: $("#close-editor-cancel"),
  scriptErrorDialog: $("#script-error-dialog"),
  scriptErrorMessage: $("#script-error-message"),
  scriptErrorDismiss: $("#script-error-dismiss"),
  research: $("#research-overlay"),
  researchToggle: $("#research-toggle"),
  researchViewport: $("#research-viewport"),
  researchCanvas: $("#research-canvas"),
  researchConnectors: $("#research-connectors"),
  researchNodes: $("#research-nodes"),
  researchTooltip: $("#research-tooltip"),
  guide: $("#guide-window"),
  guideBack: $("#guide-back"),
  guideTitle: $("#guide-title"),
  guideContent: $("#guide-content"),
  guideToggle: $("#guide-toggle"),
  guideClose: $("#guide-close"),
  account: $("#account-overlay"),
  accountForm: $("#account-form"),
  accountHeading: $("#account-heading"),
  username: $("#username-input"),
  password: $("#password-input"),
  confirm: $("#confirm-input"),
  confirmLabel: $("#confirm-label"),
  accountError: $("#account-error"),
  accountSubmit: $("#account-submit"),
  accountMode: $("#account-mode"),
  accountTag: $("#account-tag"),
  developerToggle: $("#developer-toggle"),
  developerOverlay: $("#developer-overlay"),
  developerForm: $("#developer-form"),
  developerResourceFields: $("#developer-resource-fields"),
  developerError: $("#developer-error"),
  developerCancel: $("#developer-cancel"),
};

const scene = new THREE.Scene();
scene.background = new THREE.Color("#78868c");
scene.fog = new THREE.Fog("#78868c", 12, 28);
const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 100);
camera.position.set(5.5, 7, 7);
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.75));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;
elements.canvas.append(renderer.domElement);

scene.add(new THREE.HemisphereLight("#dbe8d4", "#394345", 2.0));
const sunlight = new THREE.DirectionalLight("#fff0d5", 3.0);
sunlight.position.set(-5, 10, 6);
sunlight.castShadow = true;
sunlight.shadow.mapSize.set(1024, 1024);
scene.add(sunlight);

const groundRoot = new THREE.Group();
const cropRoot = new THREE.Group();
const droneRoot = new THREE.Group();
const pigDroneRoot = new THREE.Group();
const effectRoot = new THREE.Group();
scene.add(groundRoot, cropRoot, droneRoot, pigDroneRoot, effectRoot);
let droneRotors = [];
let droneBody;
let droneFlipAnimation = null;
let pigDroneBody;
let pigDroneRotors = [];
let pigDroneOrbitAngle = 0;
let pigDroneCollectAnimation = null;
let renderedWorldSize = "";
const groundTiles = new Map();
const cropTiles = new Map();
const harvestEffects = [];
const fieldRaycaster = new THREE.Raycaster();
const fieldPointer = new THREE.Vector2();
const fieldSelectionFrame = new THREE.LineSegments(
  new THREE.EdgesGeometry(new THREE.BoxGeometry(0.98, 0.02, 0.98)),
  new THREE.LineBasicMaterial({ color: "#ffffff" }),
);
fieldSelectionFrame.visible = false;
scene.add(fieldSelectionFrame);
let droneVisualPosition = null;
let droneMoveAnimation = null;
let droneHarvestAnimation = null;
let handledActionCount = 0;
let session;
let gameData;
let isAuthenticated = false;
let isDeveloper = false;
let accountMode = "login";
let idleTicks = 0;
let lastFrame = performance.now();
let frameBudget = 0;
let activeController = null;
let activeEditor = null;
let editorWindows = [];
let mainEditor = null;
let nextEditorId = 1;
let pendingClosePanel = null;
let panelZIndex = 1;
const textMeasureContext = document.createElement("canvas").getContext("2d");
let editorSizeSaveFrame = null;
let pointerStart = null;
let selectedField = null;
let selectedFieldTooltipPoint = null;
let researchSnapshot = "";
let researchTreeBuilt = false;
let researchZoom = 1;
let researchPan = { x: 0, y: 0 };
let researchPointer = null;
let guideHistory = [];
let guideZIndex = 20;
const SUPPORTED_GUIDE_NODES = new Set([
  "Loops", "Variables", "Operators", "Lists", "Dictionaries", "Functions",
  "Plant", "Expand", "Expand_2", "Senses", "Speed", "Costs", "Timing",
  "Utilities", "Grass", "Carrots", "Watering",
]);
let worldRenderTimer = null;
let cameraView = { angle: 0.67, radius: 9.5 };
const cameraPan = new THREE.Vector3();
const cameraRight = new THREE.Vector3();
const cameraUp = new THREE.Vector3();
const cameraPanPixels = { x: 0, y: 0 };
let lastWorldExtent = 0;

function formatCount(amount) {
  if (amount < 1000) return String(amount);
  const units = [[1e12, "T"], [1e9, "B"], [1e6, "M"], [1e3, "K"]];
  const [base, suffix] = units.find(([divisor]) => amount >= divisor);
  const value = amount < base * 10
    ? `${Math.floor(amount * 10 / base) / 10}`
    : `${Math.floor(amount / base)}`;
  return `${value}${suffix}`;
}

function gameDuration(milliseconds) {
  return Math.max(
    1,
    milliseconds / (GAME_SPEED_MULTIPLIER * (session?.progression.speedMultiplier() ?? 1)),
  );
}

function createResourceHud() {
  elements.resources.replaceChildren();
  for (const item of RESOURCE_NAMES) {
    const group = document.createElement("div");
    group.className = "resource";
    const name = document.createElement("span");
    name.className = "resource-name";
    name.textContent = item.toUpperCase();
    const value = document.createElement("span");
    value.className = "resource-value";
    value.dataset.resource = item;
    value.textContent = "0";
    group.append(name, value);
    elements.resources.append(group);
  }
}

function clearGroup(group) {
  for (const child of [...group.children]) {
    child.traverse((object) => {
      object.geometry?.dispose();
      if (Array.isArray(object.material)) object.material.forEach((material) => material.dispose());
      else object.material?.dispose();
    });
    group.remove(child);
  }
}

function removeCropGroup(group) {
  clearGroup(group);
  cropRoot.remove(group);
}

function makeMaterial(color, roughness = 0.88) {
  return new THREE.MeshStandardMaterial({ color, roughness, metalness: 0.02 });
}

function addBox(name, position, size, color, parent = cropRoot) {
  const geometry = new THREE.BoxGeometry(...size);
  const mesh = new THREE.Mesh(geometry, makeMaterial(color));
  mesh.name = name;
  mesh.position.set(...position);
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  parent.add(mesh);
  return mesh;
}

function createCrop(x, y, tile) {
  if (!tile.entity) return;
  const px = x - (session.world.width - 1) / 2;
  const pz = y - (session.world.height - 1) / 2;
  const color = COLORS.crop[tile.entity] ?? "#70a252";
  const group = new THREE.Group();
  group.name = `crop-${x}-${y}`;
  group.position.set(px, 0.031, pz);

  if (tile.entity === "grass") {
    const grass = createLowPolyGrass(x * session.world.height + y);
    group.add(grass);
  } else if (tile.entity === "bush") {
    group.add(createLowPolyBush());
  } else if (tile.entity === "tree") {
    addBox(`trunk-${x}-${y}`, [0, 0.296, 0], [0.16, 0.592, 0.16], "#79573c", group);
    addBox(`canopy-${x}-${y}`, [0, 0.86, 0], [0.55, 0.7, 0.55], color, group);
  } else if (tile.entity === "carrot") {
    addBox(`carrot-${x}-${y}`, [0, 0.311, 0], [0.19, 0.622, 0.19], color, group);
    addBox(`carrot-leaves-${x}-${y}`, [0, 0.681, 0], [0.22, 0.12, 0.22], "#6d9d47", group);
  } else {
    addBox(
      `${tile.entity}-${x}-${y}`,
      [0, 0.466, 0],
      [0.43, 0.925, 0.43],
      color,
      group,
    );
  }
  cropRoot.add(group);
  return group;
}

function renderWorld() {
  const { world } = session;
  const worldSize = `${world.width}x${world.height}`;
  const worldSizeChanged = renderedWorldSize !== worldSize;
  if (worldSizeChanged) {
    clearGroup(groundRoot);
    groundTiles.clear();
    for (const entry of cropTiles.values()) removeCropGroup(entry.group);
    cropTiles.clear();
    if (selectedField && (
      selectedField.x >= world.width || selectedField.y >= world.height
    )) clearSelectedField();
  }
  for (let x = 0; x < world.width; x += 1) {
    for (let y = 0; y < world.height; y += 1) {
      const tile = world.tile(x, y);
      const px = x - (world.width - 1) / 2;
      const pz = y - (world.height - 1) / 2;
      const key = `${x},${y}`;
      let fieldTile = groundTiles.get(key);
      if (!fieldTile) {
        const asset = createLowPolyFieldTile(x * world.height + y);
        asset.group.position.set(px, 0, pz);
        groundRoot.add(asset.group);
        fieldTile = { ...asset, ground: null, pickMesh: null };
        groundTiles.set(key, fieldTile);
      }
      if (fieldTile.ground !== tile.ground) {
        fieldTile.pickMesh = fieldTile.setGround(tile.ground);
        fieldTile.pickMesh.userData.tile = { x, y };
        fieldTile.ground = tile.ground;
      }

      const crop = cropTiles.get(key);
      if (tile.entity === null) {
        if (crop) {
          removeCropGroup(crop.group);
          cropTiles.delete(key);
        }
      } else if (!crop || crop.entity !== tile.entity) {
        if (crop) removeCropGroup(crop.group);
        const group = createCrop(x, y, tile);
        cropTiles.set(key, { entity: tile.entity, group });
      }
    }
  }
  if (selectedField) updateFieldSelectionFrame();
  renderedWorldSize = worldSize;
  updateCropGrowth();
  if (!droneBody) {
    const drone = createLowPolyDrone();
    droneBody = drone.body;
    droneBody.position.y = 0.47;
    droneRotors = drone.rotors;
    droneRoot.add(droneBody);
  }
  if (!pigDroneBody) {
    const pigDrone = createLowPolyPigDrone();
    pigDroneBody = pigDrone.body;
    pigDroneRotors = pigDrone.rotors;
    pigDroneRoot.add(pigDroneBody);
  }
  updatePigDronePosition(performance.now());
  updateDronePosition(performance.now());

  const extent = Math.max(world.width, world.height, 2);
  if (extent !== lastWorldExtent) {
    cameraView.radius = Math.max(6.2, extent * 1.65);
    lastWorldExtent = extent;
  }
  updateCamera();
  updateHud();
}

function updateCropGrowth() {
  for (const [key, crop] of cropTiles) {
    const [x, y] = key.split(",").map(Number);
    const tile = session.world.tile(x, y);
    if (!tile.entity || tile.entity !== crop.entity) continue;
    const definition = session.world.defs[tile.entity];
    const growth = Math.min(1, tile.age / Math.max(1, definition.grow_ticks));
    crop.group.scale.y = (0.22 + 0.52 * growth) / 0.74;
  }
}

function updateDronePosition(now = performance.now()) {
  if (!droneBody) return;
  let tileX = session.drone.x;
  let tileY = session.drone.y;
  if (droneMoveAnimation) {
    const progress = Math.min(1, (now - droneMoveAnimation.startedAt) / droneMoveAnimation.duration);
    if (droneMoveAnimation.wrapTo) {
      const switchPoint = 0.45;
      droneRoot.visible = progress < switchPoint || progress > switchPoint + 0.1;
      if (progress <= switchPoint) {
        const edgeProgress = progress / switchPoint;
        const eased = edgeProgress * edgeProgress * (3 - 2 * edgeProgress);
        tileX = droneMoveAnimation.from.x + droneMoveAnimation.delta.x * eased * 0.35;
        tileY = droneMoveAnimation.from.y + droneMoveAnimation.delta.y * eased * 0.35;
      } else {
        tileX = droneMoveAnimation.wrapTo.x;
        tileY = droneMoveAnimation.wrapTo.y;
      }
    } else {
      const eased = progress * progress * (3 - 2 * progress);
      tileX = droneMoveAnimation.from.x + droneMoveAnimation.delta.x * eased;
      tileY = droneMoveAnimation.from.y + droneMoveAnimation.delta.y * eased;
      droneRoot.visible = true;
    }
    if (progress >= 1) droneMoveAnimation = null;
  } else {
    droneRoot.visible = true;
  }
  droneVisualPosition = { x: tileX, y: tileY };
  const px = tileX - (session.world.width - 1) / 2;
  const pz = tileY - (session.world.height - 1) / 2;
  const bob = session.running ? Math.sin(now * 0.008) * 0.025 : 0;
  droneRoot.position.set(px, DRONE_HOVER_HEIGHT + bob, pz);
  if (droneHarvestAnimation) {
    const progress = (now - droneHarvestAnimation.startedAt) / droneHarvestAnimation.duration;
    if (progress >= 1) {
      droneHarvestAnimation = null;
      droneBody.position.y = 0.47;
      droneBody.rotation.x = 0;
    } else {
      droneBody.position.y = 0.47 - Math.sin(progress * Math.PI) * 0.1;
      droneBody.rotation.x = Math.sin(progress * Math.PI) * 0.12;
    }
  }
  if (droneFlipAnimation) {
    const progress = Math.min(1, (now - droneFlipAnimation.startedAt) / 1000);
    if (progress >= 1) {
      droneFlipAnimation = null;
      droneBody.rotation.x = 0;
    } else {
      droneBody.rotation.x = progress * Math.PI * 2;
    }
  }
}

function updatePigDronePosition(now) {
  if (!pigDroneBody || !session) return;
  const halfWidth = session.world.width / 2 + 1.05;
  const halfHeight = session.world.height / 2 + 1.05;
  const bob = Math.sin(now * 0.0025) * 0.07;
  const x = Math.cos(pigDroneOrbitAngle) * halfWidth;
  const z = Math.sin(pigDroneOrbitAngle) * halfHeight;
  pigDroneRoot.position.set(x, PIG_DRONE_HOVER_HEIGHT + bob, z);
  pigDroneRoot.rotation.y = Math.atan2(
    -halfWidth * Math.sin(pigDroneOrbitAngle),
    halfHeight * Math.cos(pigDroneOrbitAngle),
  );

  if (pigDroneCollectAnimation) {
    const progress = (now - pigDroneCollectAnimation.startedAt) / pigDroneCollectAnimation.duration;
    if (progress >= 1) {
      pigDroneCollectAnimation = null;
      pigDroneBody.scale.setScalar(1);
      pigDroneBody.rotation.z = 0;
    } else {
      const pulse = Math.sin(progress * Math.PI);
      pigDroneBody.scale.setScalar(1 + pulse * 0.08);
      pigDroneBody.rotation.z = pulse * 0.08;
    }
  }
}

function handleNewActions() {
  while (handledActionCount < session.log.length) {
    const action = session.log[handledActionCount];
    handledActionCount += 1;
    if (action.name === "move" && action.success) {
      const direction = {
        north: { x: 0, y: 1 },
        east: { x: 1, y: 0 },
        south: { x: 0, y: -1 },
        west: { x: -1, y: 0 },
      }[action.args[0]];
      if (!direction) continue;
      const from = action.from ?? droneVisualPosition ?? { x: session.drone.x, y: session.drone.y };
      const destination = action.to ?? { x: session.drone.x, y: session.drone.y };
      const crossesEdge = (
        from.x + direction.x < 0 || from.x + direction.x >= session.world.width
        || from.y + direction.y < 0 || from.y + direction.y >= session.world.height
      ) && (destination.x !== from.x || destination.y !== from.y);
      if (from.x === destination.x && from.y === destination.y) {
        droneMoveAnimation = null;
        droneVisualPosition = from;
        continue;
      }
      const ticks = session.costs.actions.move.success;
      droneMoveAnimation = {
        from,
        delta: direction,
        ...(crossesEdge ? { wrapTo: destination } : {}),
        startedAt: performance.now(),
        duration: gameDuration(ticks / TICKS_PER_SECOND * 1000),
      };
    } else if (action.name === "do_a_flip" && action.success) {
      droneFlipAnimation = { startedAt: performance.now() };
    } else if (action.name === "harvest" && action.success && session.harvestEvent) {
      startHarvestAnimation(session.drone.x, session.drone.y, session.harvestEvent);
      droneHarvestAnimation = {
        startedAt: performance.now(),
        duration: gameDuration(360),
      };
      if (Object.keys(session.harvestEvent.yields).length > 0) {
        pigDroneCollectAnimation = {
          startedAt: performance.now(),
          duration: gameDuration(500),
        };
      }
    } else if (action.name === "clear" && action.success) {
      droneMoveAnimation = null;
      droneVisualPosition = { x: 0, y: 0 };
    }
  }
}

function startHarvestAnimation(x, y, event) {
  const group = new THREE.Group();
  const world = session.world;
  const source = new THREE.Vector3(
    x - (world.width - 1) / 2,
    0.08,
    y - (world.height - 1) / 2,
  );
  group.position.set(
    source.x,
    source.y,
    source.z,
  );
  group.userData.collect = Object.keys(event.yields).length > 0;
  const colors = Object.keys(event.yields).length
    ? Object.keys(event.yields).map((item) => ({
      hay: "#d6bf70",
      wood: "#a6784b",
      carrot: "#d78745",
    }[item] ?? "#b7d879"))
    : ["#b7d879"];
  for (let index = 0; index < 7; index += 1) {
    const angle = (Math.PI * 2 * index) / 7;
    const material = new THREE.MeshStandardMaterial({
      color: colors[index % colors.length],
      emissive: colors[index % colors.length],
      emissiveIntensity: 0.25,
      transparent: true,
    });
    const particle = new THREE.Mesh(new THREE.BoxGeometry(0.09, 0.09, 0.09), material);
    particle.position.set(0, 0.2, 0);
    particle.userData.velocity = { x: Math.cos(angle), z: Math.sin(angle) };
    particle.userData.startOffset = {
      x: Math.cos(angle) * 0.08,
      y: 0.2,
      z: Math.sin(angle) * 0.08,
    };
    particle.castShadow = true;
    group.add(particle);
  }
  const ringMaterial = new THREE.MeshStandardMaterial({
    color: "#d6bf70",
    emissive: "#d6bf70",
    emissiveIntensity: 0.35,
    transparent: true,
  });
  const ring = new THREE.Mesh(new THREE.TorusGeometry(0.2, 0.025, 6, 20), ringMaterial);
  ring.rotation.x = Math.PI / 2;
  ring.position.y = 0.025;
  ring.userData.effectType = "ring";
  group.add(ring);
  effectRoot.add(group);
  harvestEffects.push({
    group,
    startedAt: performance.now(),
    duration: gameDuration(group.userData.collect ? 850 : 560),
  });
}

function updateHarvestAnimations(now) {
  for (let index = harvestEffects.length - 1; index >= 0; index -= 1) {
    const effect = harvestEffects[index];
    const progress = Math.min(1, (now - effect.startedAt) / effect.duration);
    for (const particle of effect.group.children) {
      if (particle.userData.effectType === "ring") {
        particle.scale.setScalar(0.5 + progress * 2);
        particle.material.opacity = 1 - progress;
        continue;
      }
      const velocity = particle.userData.velocity;
      if (effect.group.userData.collect) {
        const target = pigDroneRoot.position.clone().sub(effect.group.position);
        const start = particle.userData.startOffset;
        particle.position.set(
          THREE.MathUtils.lerp(start.x, target.x, progress),
          THREE.MathUtils.lerp(start.y, target.y, progress)
            + Math.sin(progress * Math.PI) * 0.42,
          THREE.MathUtils.lerp(start.z, target.z, progress),
        );
        particle.material.opacity = progress > 0.82
          ? 1 - (progress - 0.82) / 0.18
          : 1;
      } else {
        particle.position.x = velocity.x * progress * 0.58;
        particle.position.y = 0.2 + progress * (0.45 + velocity.x * 0.12);
        particle.position.z = velocity.z * progress * 0.58;
        particle.material.opacity = 1 - progress;
      }
      particle.rotation.set(progress * 4, progress * 5, progress * 3);
    }
    if (!effect.group.userData.collect) {
      effect.group.scale.setScalar(0.7 + progress * 0.45);
    }
    if (progress >= 1) {
      clearGroup(effect.group);
      effectRoot.remove(effect.group);
      harvestEffects.splice(index, 1);
    }
  }
}

function scheduleWorldRender() {
  if (worldRenderTimer !== null) return;
  worldRenderTimer = setTimeout(() => {
    worldRenderTimer = null;
    renderWorld();
  }, Math.max(16, gameDuration(80)));
}

function syncWorldSize() {
  elements.fieldSize.textContent = `FIELD ${session.world.height}x${session.world.width}`;
  elements.fieldCaption.textContent = `FIELD  ${session.world.height} x ${session.world.width}`;
}

function updateCamera() {
  const x = Math.sin(cameraView.angle) * cameraView.radius;
  const z = Math.cos(cameraView.angle) * cameraView.radius;
  camera.position.set(
    cameraPan.x + x,
    cameraPan.y + cameraView.radius * 1.45,
    cameraPan.z + z,
  );
  camera.lookAt(cameraPan);
  const editorScale = Math.max(0.28, Math.min(1.25, 6.2 / cameraView.radius));
  elements.editorLayer.style.transform =
    `translate(${cameraPanPixels.x}px, ${cameraPanPixels.y}px) scale(${editorScale})`;
  elements.editorLayer.dataset.scale = String(editorScale);
}

function updateFieldSelectionFrame() {
  if (!selectedField) return;
  fieldSelectionFrame.position.set(
    selectedField.x - (session.world.width - 1) / 2,
    0.052,
    selectedField.y - (session.world.height - 1) / 2,
  );
  fieldSelectionFrame.visible = true;
}

function positionFieldTooltip() {
  if (!selectedFieldTooltipPoint) return;
  const workspaceRect = $("#workspace").getBoundingClientRect();
  const tooltip = elements.fieldTooltip;
  const left = selectedFieldTooltipPoint.x + 16;
  const top = selectedFieldTooltipPoint.y + 16;
  tooltip.style.left = `${Math.max(12, Math.min(left, workspaceRect.width - tooltip.offsetWidth - 12))}px`;
  tooltip.style.top = `${Math.max(12, Math.min(top, workspaceRect.height - tooltip.offsetHeight - 12))}px`;
}

function refreshSelectedFieldTooltip() {
  if (!selectedField || elements.fieldTooltip.classList.contains("hidden")) return;
  const { x, y } = selectedField;
  const tile = session.world.tiles[x]?.[y];
  if (!tile) {
    clearSelectedField();
    return;
  }
  const plant = tile.entity ? session.world.defs[tile.entity] : null;
  const progress = plant
    ? Math.min(1, tile.age / Math.max(1, plant.grow_ticks))
    : null;
  const growthText = progress === null
    ? "N/A"
    : `${Math.floor(progress * 100)}% · ${progress >= 1 ? "READY TO HARVEST" : "GROWING"}`;
  const details = [
    ["COORDINATES", `X: ${x}  ·  Y: ${y}`],
    ["PLANT", tile.entity ? tile.entity.toUpperCase() : "NONE"],
    ["GROWTH", growthText],
    ["WATER", `${Math.round(tile.water * 100)}%`],
    ["GROUND", tile.ground.toUpperCase()],
  ];
  elements.fieldTooltip.replaceChildren();
  const title = document.createElement("strong");
  title.textContent = `FIELD ${x}, ${y}`;
  elements.fieldTooltip.append(title);
  for (const [label, value] of details) {
    const row = document.createElement("div");
    row.className = "field-tooltip-row";
    const key = document.createElement("span");
    key.textContent = label;
    const detail = document.createElement("b");
    detail.textContent = value;
    row.append(key, detail);
    elements.fieldTooltip.append(row);
  }
  positionFieldTooltip();
}

function clearSelectedField() {
  selectedField = null;
  selectedFieldTooltipPoint = null;
  fieldSelectionFrame.visible = false;
  elements.fieldTooltip.classList.add("hidden");
}

function selectFieldAtPointer(event) {
  const rect = renderer.domElement.getBoundingClientRect();
  fieldPointer.set(
    ((event.clientX - rect.left) / rect.width) * 2 - 1,
    -((event.clientY - rect.top) / rect.height) * 2 + 1,
  );
  fieldRaycaster.setFromCamera(fieldPointer, camera);
  const [hit] = fieldRaycaster.intersectObjects(
    [...groundTiles.values()].map((tile) => tile.pickMesh),
    false,
  );
  if (!hit?.object.userData.tile) {
    clearSelectedField();
    return;
  }
  selectedField = { ...hit.object.userData.tile };
  const workspaceRect = $("#workspace").getBoundingClientRect();
  selectedFieldTooltipPoint = {
    x: event.clientX - workspaceRect.left,
    y: event.clientY - workspaceRect.top,
  };
  updateFieldSelectionFrame();
  elements.fieldTooltip.classList.remove("hidden");
  refreshSelectedFieldTooltip();
}

function updateHud() {
  if (!session) return;
  for (const value of document.querySelectorAll("[data-resource]")) {
    const item = value.dataset.resource;
    value.textContent = formatCount(session.inventory.count(item));
  }
  elements.tick.textContent = `TICK ${String(session.tickCount).padStart(6, "0")}`;
  elements.fieldSize.textContent = `FIELD ${session.world.height}x${session.world.width}`;
  elements.fieldCaption.textContent = `FIELD  ${session.world.height} x ${session.world.width}`;
  const tile = session.tile;
  const waterStatus = `WATER ${Math.round(tile.water * 100)}%`;
  if (!tile.entity) {
    elements.cropStatus.textContent = tile.ground === "soil"
      ? `SOIL  READY TO PLANT  ·  ${waterStatus}`
      : `GRASSLAND  TILL TO PREPARE  ·  ${waterStatus}`;
  } else {
    const def = session.world.defs[tile.entity];
    const progress = Math.min(1, tile.age / def.grow_ticks);
    elements.cropStatus.textContent = progress >= 1
      ? `${tile.entity.toUpperCase()}  READY TO HARVEST  ·  ${waterStatus}`
      : `${tile.entity.toUpperCase()}  GROWING  ${Math.floor(progress * 100)}%  ·  ${waterStatus}`;
  }
  refreshSelectedFieldTooltip();
}

function readAccounts() {
  const raw = localStorage.getItem("farmer-replica-web-accounts");
  if (raw === null) return {};
  const accounts = JSON.parse(raw);
  if (
    !accounts
    || typeof accounts !== "object"
    || Array.isArray(accounts)
    || Object.values(accounts).some((account) => (
      !account
      || typeof account.username !== "string"
      || typeof account.salt !== "string"
      || typeof account.password_hash !== "string"
    ))
  ) {
    throw new Error("Local account data is invalid.");
  }
  return accounts;
}

function validUsername(username) {
  return /^[A-Za-z0-9_]{3,20}$/.test(username);
}

function hex(bytes) {
  return [...bytes].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function hashPassword(password, saltHex) {
  const salt = Uint8Array.from(
    saltHex.match(/.{2}/g) ?? [],
    (byte) => Number.parseInt(byte, 16),
  );
  const material = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(password),
    "PBKDF2",
    false,
    ["deriveBits"],
  );
  const derived = await crypto.subtle.deriveBits(
    { name: "PBKDF2", hash: "SHA-256", salt, iterations: 310000 },
    material,
    256,
  );
  return hex(new Uint8Array(derived));
}

function equalHex(left, right) {
  if (left.length !== right.length) return false;
  let difference = 0;
  for (let index = 0; index < left.length; index += 1) {
    difference |= left.charCodeAt(index) ^ right.charCodeAt(index);
  }
  return difference === 0;
}

function setAccountMode(mode) {
  accountMode = mode;
  const registering = mode === "register";
  elements.accountHeading.textContent = registering ? "BUAT AKUN" : "MASUK";
  elements.accountSubmit.textContent = registering ? "DAFTAR" : "MASUK";
  elements.accountMode.textContent = registering
    ? "Sudah punya akun? Masuk"
    : "Belum punya akun? Daftar";
  elements.confirm.classList.toggle("hidden", !registering);
  elements.confirmLabel.classList.toggle("hidden", !registering);
  elements.confirm.required = registering;
  elements.password.autocomplete = registering ? "new-password" : "current-password";
  elements.accountError.textContent = "";
}

function createProfileSession(username, tag) {
  const saveKey = `farmer-replica-profile:${username.toLowerCase()}`;
  handledActionCount = 0;
  droneMoveAnimation = null;
  droneHarvestAnimation = null;
  droneVisualPosition = null;
  for (const effect of harvestEffects) {
    clearGroup(effect.group);
    effectRoot.remove(effect.group);
  }
  harvestEffects.length = 0;
  session = new GameSession(
    gameData.entities,
    gameData.costs,
    gameData.techTree,
    () => {
      handleNewActions();
      updateHud();
      scheduleWorldRender();
      const snapshot = JSON.stringify({
        inventory: session.inventory.items,
        unlocked: [...session.progression.unlocked],
        levels: session.progression.upgradeLevels,
      });
      if (snapshot !== researchSnapshot && !elements.research.classList.contains("hidden")) {
        researchSnapshot = snapshot;
        buildResearch();
      }
    },
    saveKey,
  );
  isAuthenticated = true;
  isDeveloper = tag === "developer";
  elements.accountTag.classList.toggle("hidden", !isDeveloper);
  elements.developerToggle.classList.toggle("hidden", !isDeveloper);
  elements.account.classList.add("hidden");
  elements.code.value = session.code;
  restoreEditorWindows();
  updateLineNumbers(mainEditor);
  renderWorld();
}

async function submitAccount(event) {
  event.preventDefault();
  elements.accountSubmit.disabled = true;
  elements.accountError.textContent = "";
  try {
    let accounts = readAccounts();
    const username = elements.username.value.trim();
    const password = elements.password.value;
    if (!validUsername(username)) {
      throw new Error("Username must be 3-20 letters, numbers, or underscores.");
    }
    if (password.length < 8 || password.length > 128) {
      throw new Error("Password must contain 8-128 characters.");
    }
    const key = username.toLowerCase();
    let account = accounts[key];
    if (accountMode === "register") {
      if (password !== elements.confirm.value) {
        throw new Error("Password confirmation does not match.");
      }
      if (account) throw new Error("That username is already registered.");
      const salt = hex(crypto.getRandomValues(new Uint8Array(16)));
      account = {
        username,
        salt,
        password_hash: await hashPassword(password, salt),
        tag: key === "admin" ? "developer" : "player",
      };
      accounts[key] = account;
      localStorage.setItem("farmer-replica-web-accounts", JSON.stringify(accounts));
    } else {
      if (!account) throw new Error("Username or password does not match.");
      const candidate = await hashPassword(password, account.salt);
      if (!equalHex(candidate, account.password_hash)) {
        throw new Error("Username or password does not match.");
      }
    }
    const expectedTag = key === "admin" || account.tag === "developer"
      ? "developer"
      : "player";
    if (account.tag !== expectedTag) {
      account = { ...account, tag: expectedTag };
      accounts[key] = account;
      localStorage.setItem("farmer-replica-web-accounts", JSON.stringify(accounts));
    }
    createProfileSession(account.username, account.tag);
    elements.password.value = "";
    elements.confirm.value = "";
  } catch (error) {
    elements.accountError.textContent = error.message;
  } finally {
    elements.accountSubmit.disabled = false;
  }
}

function openDeveloperPanel() {
  if (!isAuthenticated || !isDeveloper) return;
  elements.developerError.textContent = "";
  elements.developerResourceFields.replaceChildren();
  for (const item of RESOURCE_NAMES) {
    const label = document.createElement("label");
    label.className = "developer-resource-row";
    label.htmlFor = `developer-resource-${item}`;
    const name = document.createElement("span");
    name.textContent = item.toUpperCase();
    const input = document.createElement("input");
    input.id = `developer-resource-${item}`;
    input.name = item;
    input.type = "text";
    input.inputMode = "numeric";
    input.value = String(session.inventory.count(item));
    label.append(name, input);
    elements.developerResourceFields.append(label);
  }
  elements.developerOverlay.classList.remove("hidden");
}

function closeDeveloperPanel() {
  elements.developerOverlay.classList.add("hidden");
  elements.developerError.textContent = "";
}

function saveDeveloperResources(event) {
  event.preventDefault();
  if (!isAuthenticated || !isDeveloper || !session) {
    closeDeveloperPanel();
    return;
  }
  const resources = {};
  for (const item of RESOURCE_NAMES) {
    const input = elements.developerForm.elements.namedItem(item);
    const rawAmount = input?.value.trim() ?? "";
    const amount = Number(rawAmount);
    if (!/^\d+$/.test(rawAmount) || !Number.isSafeInteger(amount)) {
      elements.developerError.textContent = `${item.toUpperCase()} harus berupa bilangan bulat non-negatif yang aman.`;
      input?.focus();
      return;
    }
    resources[item] = amount;
  }
  Object.assign(session.inventory.items, resources);
  session.notify();
  session.save(elements.code.value);
  closeDeveloperPanel();
}

function updateLineNumbers(editor) {
  const sourceLines = editor.code.value.split("\n");
  editor.lineNumbers.textContent = Array.from({ length: sourceLines.length }, (_, i) => i + 1).join("\n");
  editor.lineNumbers.scrollTop = editor.code.scrollTop;
  editor.highlightLayer.scrollLeft = editor.code.scrollLeft;
  editor.highlightLayer.replaceChildren(...sourceLines.map((line, index) => {
    const row = document.createElement("span");
    row.className = "code-line";
    if (index + 1 === editor.currentLine) row.classList.add("current-line");
    if (index + 1 === editor.errorLine) row.classList.add("error-line");
    row.textContent = line || "\u00a0";
    return row;
  }));
  editor.highlightLayer.scrollTop = editor.code.scrollTop;
}

function highlightEditorLine(editor, line) {
  editor.currentLine = line;
  updateLineNumbers(editor);
  const lineHeight = 13 * 1.48;
  const top = Math.max(0, (line - 1) * lineHeight);
  const bottom = top + lineHeight;
  if (top < editor.code.scrollTop) editor.code.scrollTop = top;
  else if (bottom > editor.code.scrollTop + editor.code.clientHeight) {
    editor.code.scrollTop = bottom - editor.code.clientHeight;
  }
  updateLineNumbers(editor);
}

function markEditorError(editor, line) {
  editor.errorLine = Number.isInteger(line) ? line : null;
  editor.currentLine = null;
  updateLineNumbers(editor);
  if (editor.errorLine !== null) {
    highlightEditorLine(editor, editor.errorLine);
    editor.errorLine = line;
    updateLineNumbers(editor);
  }
  showScriptError(editor.errorLine, editor.lastErrorMessage);
}

function showScriptError(line, message) {
  elements.scriptErrorMessage.textContent = line
    ? `Line ${line}: ${message}`
    : message;
  elements.scriptErrorDialog.classList.remove("hidden");
  elements.scriptErrorDismiss.focus();
}

function setEditorStatus(editor, text, isError = false) {
  editor.action.textContent = text;
  editor.action.style.color = isError ? "#e18a79" : "";
}

function setEditorRunningState(running, runningEditor = null) {
  for (const editor of editorWindows) {
    editor.run.disabled = running;
    editor.stop.disabled = !running || editor !== runningEditor;
  }
}

function setupEditor(panel, primary = false) {
  const editor = {
    panel,
    code: panel.querySelector("textarea"),
    codeEditor: panel.querySelector(".code-editor"),
    lineNumbers: panel.querySelector(".line-numbers"),
    highlightLayer: panel.querySelector(".code-highlight-layer"),
    action: panel.querySelector(".action-status"),
    run: panel.querySelector(".run-button"),
    stop: panel.querySelector(".stop-button"),
    primary,
    currentLine: null,
    errorLine: null,
  };
  if (!editor.code || !editor.lineNumbers || !editor.highlightLayer || !editor.action || !editor.run || !editor.stop) {
    throw new Error("Editor window is missing a required control.");
  }
  editorWindows.push(editor);
  const resizeObserver = new ResizeObserver(() => {
    if (panel.classList.contains("minimized")) return;
    if (panel.offsetWidth > 0 && panel.offsetHeight > 0) {
      editor.lastSize = { width: panel.offsetWidth, height: panel.offsetHeight };
    }
    if (!isAuthenticated || editorSizeSaveFrame !== null) return;
    editorSizeSaveFrame = requestAnimationFrame(() => {
      editorSizeSaveFrame = null;
      saveEditorWindows();
    });
  });
  resizeObserver.observe(panel);
  if (primary) mainEditor = editor;

  editor.run.addEventListener("click", () => startScript(editor));
  editor.stop.addEventListener("click", stopScript);
  editor.code.addEventListener("input", () => {
    editor.errorLine = null;
    editor.currentLine = null;
    updateLineNumbers(editor);
    scrollEditorCaretIntoView(editor);
    saveProgress();
  });
  editor.code.addEventListener("scroll", () => syncEditorScroll(editor));
  const panelName = panel.querySelector(".panel-name");
  panelName.addEventListener("input", resizePanelName);
  panelName.addEventListener("blur", () => {
    panelName.textContent = panelName.textContent.trim() || panelName.dataset.defaultTitle;
    resizePanelName({ currentTarget: panelName });
    saveEditorWindows();
  });
  editor.code.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && event.ctrlKey) {
      event.preventDefault();
      startScript(editor);
    } else if (event.key === "Tab") {
      event.preventDefault();
      editor.code.setRangeText("    ", editor.code.selectionStart, editor.code.selectionEnd, "end");
      updateLineNumbers(editor);
      scrollEditorCaretIntoView(editor);
    } else if (event.key === "Enter") {
      const start = editor.code.selectionStart;
      const lineStart = editor.code.value.lastIndexOf("\n", start - 1) + 1;
      const currentLine = editor.code.value.slice(lineStart, start);
      const indent = currentLine.match(/^[ \t]*/)?.[0] ?? "";
      const content = currentLine.trimEnd();
      const nextIndent = !content
        ? (indent.endsWith("    ") ? indent.slice(0, -4) : "")
        : content.endsWith(":") ? `${indent}    ` : indent;
      event.preventDefault();
      editor.code.setRangeText(`\n${nextIndent}`, start, editor.code.selectionEnd, "end");
      updateLineNumbers(editor);
      scrollEditorCaretIntoView(editor);
    }
  });
  updateLineNumbers(editor);
  return editor;
}

function syncEditorScroll(editor) {
  editor.lineNumbers.scrollTop = editor.code.scrollTop;
  editor.highlightLayer.scrollTop = editor.code.scrollTop;
  editor.highlightLayer.scrollLeft = editor.code.scrollLeft;
}

function scrollEditorCaretIntoView(editor) {
  const code = editor.code;
  const beforeCaret = code.value.slice(0, code.selectionStart);
  const lines = beforeCaret.split("\n");
  const lineIndex = lines.length - 1;
  const lineText = lines[lineIndex].replace(/\t/g, "    ");
  const style = getComputedStyle(code);
  const lineHeight = Number.parseFloat(style.lineHeight);
  const paddingTop = Number.parseFloat(style.paddingTop);
  const paddingBottom = Number.parseFloat(style.paddingBottom);
  const caretTop = paddingTop + lineIndex * lineHeight;
  const visibleTop = code.scrollTop + paddingTop;
  const visibleBottom = code.scrollTop + code.clientHeight - paddingBottom;
  if (caretTop < visibleTop) {
    code.scrollTop = caretTop - paddingTop;
  } else if (caretTop + lineHeight > visibleBottom) {
    code.scrollTop = caretTop + lineHeight - code.clientHeight + paddingBottom;
  }

  textMeasureContext.font = `${style.fontSize} ${style.fontFamily}`;
  const caretWidth = Number.parseFloat(style.paddingLeft)
    + textMeasureContext.measureText(lineText).width;
  const visibleLeft = code.scrollLeft + Number.parseFloat(style.paddingLeft);
  const visibleRight = code.scrollLeft + code.clientWidth - Number.parseFloat(style.paddingRight);
  if (caretWidth < visibleLeft) {
    code.scrollLeft = caretWidth - Number.parseFloat(style.paddingLeft);
  } else if (caretWidth > visibleRight) {
    code.scrollLeft = caretWidth - code.clientWidth + Number.parseFloat(style.paddingRight);
  }
  syncEditorScroll(editor);
}

function buildResearch() {
  const preserveView = researchTreeBuilt && !elements.research.classList.contains("hidden");
  const entries = Object.entries(session.progression.tree);
  const nodesByName = new Map(entries);
  const children = new Map(entries.map(([name]) => [name, []]));
  const visualParents = new Map();
  for (const [name, node] of entries) {
    const parents = (node.visual_parents ?? node.prerequisites ?? [])
      .filter((parent) => nodesByName.has(parent));
    visualParents.set(name, parents);
    for (const parent of parents) children.get(parent).push(name);
  }

  const subtreeWidths = new Map();
  const measuring = new Set();
  function measureSubtree(name) {
    if (subtreeWidths.has(name)) return subtreeWidths.get(name);
    if (measuring.has(name)) throw new Error(`Research prerequisites contain a cycle at "${name}".`);
    measuring.add(name);
    const descendants = children.get(name);
    const childrenWidth = descendants.reduce(
      (sum, child) => sum + measureSubtree(child),
      Math.max(0, descendants.length - 1) * RESEARCH_LAYOUT.horizontalGap,
    );
    const width = Math.max(RESEARCH_NODE_SIZE.width, childrenWidth);
    measuring.delete(name);
    subtreeWidths.set(name, width);
    return width;
  }
  for (const [name] of entries) measureSubtree(name);

  const roots = entries
    .filter(([name]) => visualParents.get(name).length === 0)
    .map(([name]) => name);
  const positions = new Map();
  let deepestLevel = 0;
  function placeSubtree(name, left, level) {
    const width = subtreeWidths.get(name);
    positions.set(name, {
      x: left + (width - RESEARCH_NODE_SIZE.width) / 2,
      y: RESEARCH_LAYOUT.margin + level * (RESEARCH_NODE_SIZE.height + RESEARCH_LAYOUT.verticalGap),
    });
    deepestLevel = Math.max(deepestLevel, level);

    const descendants = children.get(name);
    const descendantsWidth = descendants.reduce(
      (sum, child) => sum + subtreeWidths.get(child),
      Math.max(0, descendants.length - 1) * RESEARCH_LAYOUT.horizontalGap,
    );
    let childLeft = left + (width - descendantsWidth) / 2;
    for (const child of descendants) {
      placeSubtree(child, childLeft, level + 1);
      childLeft += subtreeWidths.get(child) + RESEARCH_LAYOUT.horizontalGap;
    }
  }
  let rootLeft = RESEARCH_LAYOUT.margin;
  for (const root of roots) {
    placeSubtree(root, rootLeft, 0);
    rootLeft += subtreeWidths.get(root) + RESEARCH_LAYOUT.rootGap;
  }
  researchCanvasSize = {
    width: Math.max(1600, rootLeft - RESEARCH_LAYOUT.rootGap + RESEARCH_LAYOUT.margin),
    height: Math.max(
      1200,
      RESEARCH_LAYOUT.margin * 2
        + deepestLevel * (RESEARCH_NODE_SIZE.height + RESEARCH_LAYOUT.verticalGap)
        + RESEARCH_NODE_SIZE.height,
    ),
  };

  elements.researchNodes.replaceChildren();
  elements.researchConnectors.replaceChildren();
  elements.researchConnectors.setAttribute(
    "viewBox",
    `0 0 ${researchCanvasSize.width} ${researchCanvasSize.height}`,
  );
  elements.researchCanvas.style.width = `${researchCanvasSize.width}px`;
  elements.researchCanvas.style.height = `${researchCanvasSize.height}px`;

  for (const [name, node] of entries) {
    const position = positions.get(name);
    const status = session.progression.status(name);
    const cost = session.progression.currentCost(name);
    const affordable = status === "available" && session.progression.affordable(name);
    const button = document.createElement("button");
    button.type = "button";
    button.className = `research-node ${status}${affordable ? " affordable" : ""}`;
    button.style.left = `${position.x}px`;
    button.style.top = `${position.y}px`;
    button.dataset.researchName = name;
    const levels = node.levels;
    const currentLevel = levels ? session.progression.upgradeLevels[name] ?? 0 : 0;
    const maxLevel = levels?.length ?? 0;
    button.setAttribute(
      "aria-label",
      levels
        ? `${name.replaceAll("_", " ")}: level ${currentLevel} of ${maxLevel}, ${status}`
        : `${name.replaceAll("_", " ")}: ${status}`,
    );
    const title = document.createElement("span");
    title.textContent = name.replaceAll("_", " ").toUpperCase();
    const sub = document.createElement("small");
    const costText = cost
      ? Object.entries(cost).map(([item, value]) => `${formatCount(value)} ${item.toUpperCase()}`).join(" · ")
      : "";
    sub.textContent = levels
      ? `${currentLevel}/${maxLevel}${costText ? ` · ${costText}` : " · MAX"}`
      : status === "unlocked"
        ? "UNLOCKED"
        : costText || status.toUpperCase();
    button.append(title, sub);
    button.addEventListener("pointerenter", (event) => showResearchTooltip(name, node, event));
    button.addEventListener("pointermove", positionResearchTooltip);
    button.addEventListener("pointerleave", hideResearchTooltip);
    button.addEventListener("click", () => {
      if (status !== "available" || !affordable || !session.unlock(name)) return;
      session.save(elements.code.value);
      setEditorStatus(
        mainEditor,
        levels
          ? `UPGRADED: ${name.toUpperCase()} ${currentLevel + 1}/${maxLevel}`
          : `UNLOCKED: ${name.toUpperCase()}`,
      );
      renderWorld();
      buildResearch();
    });
    elements.researchNodes.append(button);
  }

  for (const [parentName, childNames] of children) {
    if (childNames.length === 0) continue;
    const parentPosition = positions.get(parentName);
    const parentX = parentPosition.x + RESEARCH_NODE_SIZE.width / 2;
    const branchY = parentPosition.y + RESEARCH_NODE_SIZE.height
      + RESEARCH_LAYOUT.verticalGap / 2;
    const childXs = childNames.map((name) => (
      positions.get(name).x + RESEARCH_NODE_SIZE.width / 2
    ));
    const firstChildY = positions.get(childNames[0]).y;
    const connector = document.createElementNS("http://www.w3.org/2000/svg", "path");
    if (childNames.length === 1) {
      connector.setAttribute("d", `M ${parentX} ${parentPosition.y + RESEARCH_NODE_SIZE.height} V ${firstChildY}`);
    } else {
      const branch = [
        `M ${parentX} ${parentPosition.y + RESEARCH_NODE_SIZE.height} V ${branchY}`,
        `M ${Math.min(...childXs)} ${branchY} H ${Math.max(...childXs)}`,
        ...childXs.map((x) => `M ${x} ${branchY} V ${firstChildY}`),
      ].join(" ");
      connector.setAttribute("d", branch);
    }
    connector.classList.add("research-connector");
    elements.researchConnectors.append(connector);
  }

  researchTreeBuilt = true;
  if (preserveView) updateResearchTransform();
  else resizeResearchView();
}

function showResearchTooltip(name, node, event) {
  const status = session.progression.status(name);
  const cost = session.progression.currentCost(name) ?? {};
  const costText = Object.entries(cost)
    .map(([item, amount]) => `${formatCount(amount)} ${item.toUpperCase()}`)
    .join(" · ") || "NO COST";
  elements.researchTooltip.replaceChildren();
  const title = document.createElement("strong");
  title.textContent = name.replaceAll("_", " ");
  const description = document.createElement("p");
  description.textContent = node.usage ?? node.description ?? "Research unlock.";
  const details = document.createElement("small");
  if (node.levels) {
    const currentLevel = session.progression.upgradeLevels[name] ?? 0;
    const maxLevel = node.levels.length;
    const nextAction = status === "unlocked"
      ? "MAX LEVEL"
      : status === "locked"
        ? "LOCKED"
        : session.progression.affordable(name)
          ? `CLICK TO UPGRADE ${currentLevel + 1}/${maxLevel}`
          : "NEED RESOURCES";
    details.textContent = `LEVEL ${currentLevel}/${maxLevel} · ${costText} · ${nextAction}`;
  } else {
    details.textContent = status === "available" && session.progression.affordable(name)
      ? `${costText} · CLICK TO UNLOCK`
      : `${costText} · ${status.toUpperCase()}`;
  }
  elements.researchTooltip.append(title, description, details);
  elements.researchTooltip.classList.remove("hidden");
  positionResearchTooltip(event);
}

function positionResearchTooltip(event) {
  const rect = elements.researchViewport.getBoundingClientRect();
  const tooltip = elements.researchTooltip;
  const left = Math.min(event.clientX - rect.left + 18, rect.width - tooltip.offsetWidth - 12);
  const top = Math.min(event.clientY - rect.top + 18, rect.height - tooltip.offsetHeight - 12);
  tooltip.style.left = `${Math.max(12, left)}px`;
  tooltip.style.top = `${Math.max(12, top)}px`;
}

function hideResearchTooltip() {
  elements.researchTooltip.classList.add("hidden");
}

function updateResearchTransform() {
  elements.researchCanvas.style.transform =
    `translate(${researchPan.x}px, ${researchPan.y}px) scale(${researchZoom})`;
}

function resizeResearchView() {
  if (elements.research.classList.contains("hidden")) return;
  const rect = elements.researchViewport.getBoundingClientRect();
  const fit = Math.min(
    (rect.width - 48) / researchCanvasSize.width,
    (rect.height - 48) / researchCanvasSize.height,
  );
  researchZoom = Math.max(0.3, Math.min(1.5, fit));
  researchPan = {
    x: (rect.width - researchCanvasSize.width * researchZoom) / 2,
    y: (rect.height - researchCanvasSize.height * researchZoom) / 2,
  };
  updateResearchTransform();
}

function setResearchMode(enabled) {
  elements.research.classList.toggle("hidden", !enabled);
  $("#workspace").classList.toggle("research-mode", enabled);
  elements.researchToggle.textContent = enabled ? "FARM" : "RESEARCH";
  hideResearchTooltip();
  if (enabled) {
    clearSelectedField();
    if (!researchTreeBuilt) buildResearch();
    else resizeResearchView();
  }
}

function setupResearchNavigation() {
  elements.researchViewport.addEventListener("pointerdown", (event) => {
    if (event.target.closest(".research-node")) return;
    researchPointer = {
      x: event.clientX,
      y: event.clientY,
      panX: researchPan.x,
      panY: researchPan.y,
    };
    elements.researchViewport.setPointerCapture(event.pointerId);
    elements.researchViewport.classList.add("dragging");
  });
  elements.researchViewport.addEventListener("pointermove", (event) => {
    if (!researchPointer) return;
    researchPan.x = researchPointer.panX + event.clientX - researchPointer.x;
    researchPan.y = researchPointer.panY + event.clientY - researchPointer.y;
    updateResearchTransform();
  });
  const stopDragging = () => {
    researchPointer = null;
    elements.researchViewport.classList.remove("dragging");
  };
  elements.researchViewport.addEventListener("pointerup", stopDragging);
  elements.researchViewport.addEventListener("pointercancel", stopDragging);
  elements.researchViewport.addEventListener("wheel", (event) => {
    event.preventDefault();
    const rect = elements.researchViewport.getBoundingClientRect();
    const pointerX = event.clientX - rect.left;
    const pointerY = event.clientY - rect.top;
    const nextZoom = Math.max(0.3, Math.min(2, researchZoom * (event.deltaY < 0 ? 1.12 : 0.89)));
    const scale = nextZoom / researchZoom;
    researchPan.x = pointerX - (pointerX - researchPan.x) * scale;
    researchPan.y = pointerY - (pointerY - researchPan.y) * scale;
    researchZoom = nextZoom;
    updateResearchTransform();
  }, { passive: false });
}

async function startScript(editor = mainEditor) {
  if (activeController) return;
  if (!editor) return;
  const source = editor.code.value;
  if (editor.primary) session.code = source;
  activeController = new AbortController();
  activeEditor = editor;
  session.controller = activeController;
  editor.errorLine = null;
  editor.currentLine = null;
  updateLineNumbers(editor);
  setEditorRunningState(true, editor);
  setEditorStatus(editor, "RUNNING");
  try {
    session.executionStartTick = session.tickCount;
    session.resetTickScheduler();
    const interpreter = new GameInterpreter(session);
    await interpreter.run(source, activeController.signal, (line) => {
      highlightEditorLine(editor, line);
      setEditorStatus(editor, `RUNNING  ·  LINE ${line}`);
    });
    if (!activeController.signal.aborted) {
      setEditorStatus(editor, "COMPLETE");
    }
  } catch (error) {
    if (error.name !== "AbortError") {
      const line = Number.isInteger(error.line) ? error.line : null;
      editor.lastErrorMessage = error.message;
      setEditorStatus(editor, line ? `ERROR · LINE ${line}` : "SCRIPT ERROR", true);
      markEditorError(editor, line);
    } else {
      setEditorStatus(editor, "STOPPED");
    }
  } finally {
    activeController = null;
    activeEditor = null;
    session.controller = null;
    setEditorRunningState(false);
    renderWorld();
    saveProgress();
  }
}

function stopScript() {
  activeController?.abort();
}

function loadCodeExample(source, message) {
  elements.code.value = source;
  updateLineNumbers(mainEditor);
  saveProgress();
  elements.guide.classList.add("hidden");
  elements.code.focus();
  setEditorStatus(mainEditor, message);
}

function openGuide() {
  guideHistory = [{ type: "home" }];
  renderGuidePage();
  panelZIndex = Math.max(panelZIndex, guideZIndex) + 1;
  guideZIndex = panelZIndex;
  elements.guide.style.zIndex = String(guideZIndex);
  elements.guide.classList.remove("hidden");
}

function closeGuide() {
  elements.guide.classList.add("hidden");
}

function guideCostText(cost = {}) {
  return Object.entries(cost)
    .map(([item, amount]) => `${formatCount(amount)} ${item.toUpperCase()}`)
    .join(" · ") || "NO COST";
}

function createGuideEntryButton(item, sectionId) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "guide-entry";
  button.dataset.guideSection = sectionId;
  button.dataset.guideItem = item.id;
  const title = document.createElement("strong");
  title.textContent = item.title;
  const summary = document.createElement("span");
  summary.textContent = item.body ?? "";
  const meta = document.createElement("small");
  meta.textContent = item.supported === false ? "WIKI REFERENCE · BELUM DIDUKUNG" : item.meta ?? "";
  button.append(title, summary, meta);
  return button;
}

function guideInfoBoxItems() {
  return Object.entries(gameData.techTree)
    .filter(([name]) => !name.startsWith("_"))
    .map(([name, node]) => ({
      id: name,
      title: name.replaceAll("_", " "),
      body: node.description ?? node.usage ?? "Research node.",
      details: node.usage,
      supported: SUPPORTED_GUIDE_NODES.has(name),
      prerequisites: node.prerequisites ?? [],
      cost: node.levels
        ? node.levels[session.progression.upgradeLevels[name] ?? 0]?.cost
        : node.cost,
      levels: node.levels,
      currentLevel: node.levels ? session.progression.upgradeLevels[name] ?? 0 : null,
      source: node.source?.url ?? `${WIKI_SOURCE}Unlocks`,
      code: node.source_code,
    }));
}

function guideCodeSnippetItems() {
  const snippets = [...CODE_SNIPPETS];
  const seenCode = new Set(snippets.map((item) => item.code).filter(Boolean));
  for (const [name, node] of Object.entries(gameData.techTree)) {
    if (name.startsWith("_") || !node.source_code || seenCode.has(node.source_code)) continue;
    seenCode.add(node.source_code);
    snippets.push({
      title: name.replaceAll("_", " "),
      body: node.usage ?? node.description ?? "Contoh kode dari data research.",
      code: node.source_code,
      requires: (node.prerequisites ?? []).join(", ") || "Tidak ada prasyarat",
      supported: SUPPORTED_GUIDE_NODES.has(name),
      source: node.example_source?.url ?? node.source?.url ?? `${WIKI_SOURCE}Unlocks`,
    });
  }
  return snippets.map((item, index) => ({ ...item, id: String(index) }));
}

function guideItems(sectionId) {
  if (sectionId === "general") return GENERAL_INFO.map((item, index) => ({ ...item, id: String(index) }));
  if (sectionId === "info-boxes") return guideInfoBoxItems();
  if (sectionId === "tool-tips") return TOOL_TIPS.map((item, index) => ({ ...item, id: String(index) }));
  if (sectionId === "other-information") return OTHER_INFORMATION.map((item, index) => ({ ...item, id: String(index) }));
  if (sectionId === "code-snippets") return guideCodeSnippetItems();
  if (sectionId === "removed") return REMOVED_ITEMS.map((item, index) => ({ ...item, id: String(index) }));
  return [];
}

function renderGuideHome(content) {
  const intro = document.createElement("p");
  intro.className = "guide-intro";
  intro.textContent = "Pilih kategori untuk membuka ringkasan, tool tips, informasi tambahan, dan contoh kode berdasarkan Wiki The Farmer Was Replaced. Materi ditulis ulang sebagai panduan; item berlabel BELUM DIDUKUNG hanya referensi.";
  content.append(intro);
  for (const section of GUIDE_SECTIONS) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "guide-category";
    button.dataset.guideSection = section.id;
    const title = document.createElement("strong");
    title.textContent = section.title;
    const description = document.createElement("span");
    description.textContent = section.description;
    button.append(title, description);
    content.append(button);
  }
  const source = document.createElement("a");
  source.className = "guide-source";
  source.href = `${WIKI_SOURCE}Main_Page`;
  source.target = "_blank";
  source.rel = "noopener noreferrer";
  source.textContent = "BUKA THE FARMER WAS REPLACED WIKI";
  content.append(source);
}

function renderGuideSection(content, route) {
  const section = GUIDE_SECTIONS.find((entry) => entry.id === route.id);
  if (!section) return;
  const intro = document.createElement("p");
  intro.className = "guide-intro";
  intro.textContent = section.description;
  content.append(intro);
  for (const item of guideItems(route.id)) {
    content.append(createGuideEntryButton(item, route.id));
  }
}

function renderGuideDetail(content, route) {
  const item = guideItems(route.sectionId).find((entry) => entry.id === route.itemId);
  if (!item) return;
  const article = document.createElement("article");
  article.className = "guide-detail";
  const status = document.createElement("span");
  status.className = `guide-status${item.supported === false ? " unsupported" : ""}`;
  status.textContent = item.supported === false ? "REFERENSI WIKI · BELUM DIDUKUNG" : "PANDUAN";
  article.append(status);
  const body = document.createElement("p");
  body.textContent = item.body ?? "";
  article.append(body);
  if (item.details) {
    const details = document.createElement("p");
    details.textContent = item.details;
    article.append(details);
  }
  if (item.unlock) {
    const unlock = document.createElement("p");
    unlock.className = "guide-meta";
    unlock.textContent = `Research: ${item.unlock}`;
    article.append(unlock);
  }
  if (item.prerequisites?.length) {
    const prerequisites = document.createElement("p");
    prerequisites.className = "guide-meta";
    prerequisites.textContent = `Prasyarat: ${item.prerequisites.join(", ")}`;
    article.append(prerequisites);
  }
  if (item.requires) {
    const requirements = document.createElement("p");
    requirements.className = "guide-meta";
    requirements.textContent = `Research yang diperlukan: ${item.requires}`;
    article.append(requirements);
  }
  if (item.currentLevel !== null && item.currentLevel !== undefined) {
    const level = document.createElement("p");
    level.className = "guide-meta";
    level.textContent = `Level saat ini: ${item.currentLevel}/${item.levels.length}`;
    article.append(level);
  }
  if (item.cost) {
    const cost = document.createElement("p");
    cost.className = "guide-meta";
    cost.textContent = `Biaya berikutnya: ${guideCostText(item.cost)}`;
    article.append(cost);
  } else if (item.levels?.length && item.currentLevel >= item.levels.length) {
    const maxLevel = document.createElement("p");
    maxLevel.className = "guide-meta";
    maxLevel.textContent = "Level maksimum sudah tercapai.";
    article.append(maxLevel);
  }
  if (item.levels?.length) {
    const levels = document.createElement("div");
    levels.className = "guide-levels";
    const heading = document.createElement("strong");
    heading.textContent = `LEVEL UPGRADE (${item.levels.length})`;
    levels.append(heading);
    item.levels.forEach((level, index) => {
      const line = document.createElement("p");
      const effect = Object.entries(level.effects ?? {})
        .map(([key, value]) => `${key.replaceAll("_", " ")}: ${value}`)
        .join(" · ");
      line.textContent = `${index + 1}. ${guideCostText(level.cost)}${effect ? ` — ${effect}` : ""}`;
      levels.append(line);
    });
    article.append(levels);
  }
  if (item.note) {
    const note = document.createElement("p");
    note.className = "guide-note";
    note.textContent = item.note;
    article.append(note);
  }
  if (item.code) {
    const code = document.createElement("pre");
    code.className = "guide-code";
    code.textContent = item.code;
    article.append(code);
  }
  if (route.sectionId === "code-snippets") {
    const load = document.createElement("button");
    load.type = "button";
    load.className = "button run-button guide-load-code";
    load.dataset.guideLoadSnippet = route.itemId;
    load.textContent = "LOAD EXAMPLE INTO EDITOR";
    if (!item.code && !item.action) load.disabled = true;
    article.append(load);
  }
  if (item.source) {
    const source = document.createElement("a");
    source.className = "guide-source";
    source.href = item.source;
    source.target = "_blank";
    source.rel = "noopener noreferrer";
    source.textContent = "SOURCE: THE FARMER WAS REPLACED WIKI";
    article.append(source);
  }
  content.append(article);
}

function renderGuidePage() {
  const route = guideHistory.at(-1) ?? { type: "home" };
  elements.guideContent.replaceChildren();
  elements.guideTitle.textContent = route.type === "home"
    ? "FIELD GUIDE"
    : route.type === "section"
      ? GUIDE_SECTIONS.find((section) => section.id === route.id)?.title ?? "FIELD GUIDE"
      : guideItems(route.sectionId).find((item) => item.id === route.itemId)?.title ?? "FIELD GUIDE";
  if (route.type === "home") renderGuideHome(elements.guideContent);
  else if (route.type === "section") renderGuideSection(elements.guideContent, route);
  else renderGuideDetail(elements.guideContent, route);
  elements.guideContent.scrollTop = 0;
}

function setupGuideNavigation() {
  elements.guideToggle.addEventListener("click", openGuide);
  elements.guideClose.addEventListener("click", closeGuide);
  elements.guideBack.addEventListener("click", () => {
    if (guideHistory.length > 1) guideHistory.pop();
    else {
      closeGuide();
      return;
    }
    renderGuidePage();
  });
  elements.guideContent.addEventListener("click", (event) => {
    const loadButton = event.target.closest("[data-guide-load-snippet]");
    if (loadButton) {
      const item = guideCodeSnippetItems().find((entry) => entry.id === loadButton.dataset.guideLoadSnippet);
      if (!item) return;
      if (item.code) loadCodeExample(item.code, `Loaded guide example: ${item.title}.`);
      return;
    }
    const entryButton = event.target.closest("[data-guide-item]");
    if (entryButton) {
      guideHistory.push({
        type: "item",
        sectionId: entryButton.dataset.guideSection,
        itemId: entryButton.dataset.guideItem,
      });
      renderGuidePage();
      return;
    }
    const sectionButton = event.target.closest("[data-guide-section]");
    if (sectionButton) {
      guideHistory.push({ type: "section", id: sectionButton.dataset.guideSection });
      renderGuidePage();
    }
  });
}

function saveProgress() {
  if (!isAuthenticated) return;
  try {
    session.save(elements.code.value);
    saveEditorWindows();
  } catch (error) {
    showScriptError(null, `Save error: ${error.message}`);
    setEditorStatus(mainEditor, "SAVE ERROR", true);
  }
}

function resizePanelName(event) {
  const name = event.currentTarget;
  const text = name.textContent || "";
  name.style.width = `${Math.max(30, Math.min(260, text.length * 7 + 8))}px`;
}

function saveEditorWindows() {
  if (!isAuthenticated) return;
  const state = {
    mainTitle: mainEditor.panel.querySelector(".panel-name").textContent.trim(),
    mainSize: mainEditor.lastSize ?? { width: 382, height: 278 },
    editors: editorWindows
      .filter((editor) => !editor.primary && !editor.panel.classList.contains("hidden"))
      .map((editor) => ({
        title: editor.panel.querySelector(".panel-name").textContent.trim(),
        code: editor.code.value,
        ...(editor.lastSize ?? { width: 382, height: 278 }),
      })),
  };
  localStorage.setItem(`${session.saveKey}:editor-windows`, JSON.stringify(state));
}

function restoreEditorWindows() {
  const raw = localStorage.getItem(`${session.saveKey}:editor-windows`);
  if (!raw) return;
  let state;
  try {
    state = JSON.parse(raw);
  } catch (error) {
    throw new Error(`Could not read saved editor windows: ${error.message}`);
  }
  if (!state || typeof state !== "object" || !Array.isArray(state.editors)) {
    throw new Error("Saved editor windows have an invalid format.");
  }
  if (typeof state.mainTitle === "string" && state.mainTitle.trim()) {
    const name = mainEditor.panel.querySelector(".panel-name");
    name.textContent = state.mainTitle.trim();
    resizePanelName({ currentTarget: name });
  }
  if (
    state.mainSize
    && Number.isFinite(state.mainSize.width)
    && Number.isFinite(state.mainSize.height)
    && state.mainSize.width > 0
    && state.mainSize.height > 0
  ) {
    mainEditor.panel.style.width = `${state.mainSize.width}px`;
    mainEditor.panel.style.height = `${state.mainSize.height}px`;
  }
  for (const saved of state.editors) {
    if (!saved || typeof saved.title !== "string" || typeof saved.code !== "string") {
      throw new Error("A saved editor window has an invalid format.");
    }
    addEditorWindow(saved);
  }
}

function setupWindowPanels() {
  for (const panel of document.querySelectorAll(".window")) setupWindowPanel(panel);
  document.addEventListener("click", (event) => {
    const minimizeButton = event.target.closest("[data-minimize]");
    const closeButton = event.target.closest("[data-close]");
    if (minimizeButton) {
      const panel = minimizeButton.dataset.minimize
        ? document.getElementById(minimizeButton.dataset.minimize)
        : minimizeButton.closest(".window");
      if (!panel) return;
      panel.classList.toggle("minimized");
      minimizeButton.textContent = panel.classList.contains("minimized") ? "□" : "_";
    }
    if (closeButton) {
      pendingClosePanel = closeButton.closest(".editor-window");
      if (pendingClosePanel) {
        const title = pendingClosePanel.querySelector(".panel-name").textContent.trim();
        elements.closeEditorMessage.textContent = `Yakin ingin menutup editor "${title}"?`;
        elements.closeEditorDialog.classList.remove("hidden");
        elements.closeEditorCancel.focus();
      }
    }
  });
  elements.closeEditorCancel.addEventListener("click", dismissCloseEditor);
  elements.closeEditorConfirm.addEventListener("click", confirmCloseEditor);
  elements.closeEditorDialog.addEventListener("click", (event) => {
    if (event.target === elements.closeEditorDialog) dismissCloseEditor();
  });
  elements.scriptErrorDismiss.addEventListener("click", () => {
    elements.scriptErrorDialog.classList.add("hidden");
  });
  elements.scriptErrorDialog.addEventListener("click", (event) => {
    if (event.target === elements.scriptErrorDialog) {
      elements.scriptErrorDialog.classList.add("hidden");
    }
  });
}

function dismissCloseEditor() {
  pendingClosePanel = null;
  elements.closeEditorDialog.classList.add("hidden");
}

function confirmCloseEditor() {
  if (!pendingClosePanel) return;
  if (activeEditor?.panel === pendingClosePanel) stopScript();
  pendingClosePanel.classList.add("hidden");
  dismissCloseEditor();
  saveProgress();
}

function setupWindowPanel(panel) {
  const title = panel.querySelector(".window-title");
  if (!title || panel.dataset.panelReady) return;
  panel.dataset.panelReady = "true";
  const name = panel.querySelector(".panel-name");
  if (name) {
    name.dataset.defaultTitle = name.textContent.trim();
    resizePanelName({ currentTarget: name });
    name.addEventListener("blur", () => {
      name.textContent = name.textContent.trim() || name.dataset.defaultTitle;
    });
    name.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        name.blur();
      }
    });
  }
  {
    let drag = null;
    title.addEventListener("pointerdown", (event) => {
      if (event.target.closest("button, [contenteditable='true']")) return;
      const point = editorLayerPoint(event.clientX, event.clientY);
      drag = { x: point.x - panel.offsetLeft, y: point.y - panel.offsetTop };
      title.setPointerCapture(event.pointerId);
      panel.style.zIndex = String(++panelZIndex);
    });
    title.addEventListener("pointermove", (event) => {
      if (!drag) return;
      const point = editorLayerPoint(event.clientX, event.clientY);
      panel.style.left = `${point.x - drag.x}px`;
      panel.style.top = `${point.y - drag.y}px`;
      panel.style.right = "auto";
      panel.style.bottom = "auto";
    });
    const endDrag = () => { drag = null; };
    title.addEventListener("pointerup", endDrag);
    title.addEventListener("pointercancel", endDrag);

  }
}

function editorLayerPoint(clientX, clientY) {
  const rect = $("#workspace").getBoundingClientRect();
  const scale = Number(elements.editorLayer.dataset.scale) || 1;
  const centerX = rect.width / 2;
  const centerY = rect.height / 2;
  return {
    x: centerX + (clientX - rect.left - cameraPanPixels.x - centerX) / scale,
    y: centerY + (clientY - rect.top - cameraPanPixels.y - centerY) / scale,
  };
}

function addEditorWindow(saved = {}) {
  const template = $("#editor-template");
  const panel = template.content.firstElementChild.cloneNode(true);
  const id = `editor-panel-${nextEditorId++}`;
  panel.id = id;
  const extraEditorIndex = editorWindows.filter((editor) => !editor.primary).length;
  const top = Math.min(72 + extraEditorIndex * 195, Math.max(72, $("#workspace").clientHeight - 220));
  panel.style.top = `${top}px`;
  panel.style.left = "20px";
  panel.style.right = "auto";
  if (Number.isFinite(saved.width) && saved.width > 0) {
    panel.style.width = `${saved.width}px`;
  }
  if (Number.isFinite(saved.height) && saved.height > 0) {
    panel.style.height = `${saved.height}px`;
  }
  panel.querySelector("textarea").value = saved.code ?? "harvest()";
  const panelName = panel.querySelector(".panel-name");
  panelName.textContent = saved.title ?? "DRONE CODE";
  const minimize = panel.querySelector("[data-minimize]");
  const close = panel.querySelector("[data-close]");
  minimize.dataset.minimize = id;
  close.dataset.close = id;
  elements.editorLayer.append(panel);
  setupWindowPanel(panel);
  const editor = setupEditor(panel);
  saveProgress();
  setEditorRunningState(Boolean(activeController), activeEditor);
  panel.style.zIndex = String(++panelZIndex);
}

function setupCamera() {
  renderer.domElement.addEventListener("pointerdown", (event) => {
    if (event.button !== 0) return;
    pointerStart = {
      x: event.clientX,
      y: event.clientY,
      startX: event.clientX,
      startY: event.clientY,
      moved: false,
    };
    renderer.domElement.setPointerCapture(event.pointerId);
  });
  renderer.domElement.addEventListener("pointermove", (event) => {
    if (selectedField && !elements.fieldTooltip.classList.contains("hidden")) {
      const workspaceRect = $("#workspace").getBoundingClientRect();
      selectedFieldTooltipPoint = {
        x: event.clientX - workspaceRect.left,
        y: event.clientY - workspaceRect.top,
      };
      positionFieldTooltip();
    }
    if (!pointerStart) return;
    let dx = event.clientX - pointerStart.x;
    let dy = event.clientY - pointerStart.y;
    const totalX = event.clientX - pointerStart.startX;
    const totalY = event.clientY - pointerStart.startY;
    if (!pointerStart.moved && Math.hypot(totalX, totalY) > 4) {
      pointerStart.moved = true;
      dx = totalX;
      dy = totalY;
    }
    if (pointerStart.moved) {
      camera.updateMatrixWorld();
      cameraRight.setFromMatrixColumn(camera.matrixWorld, 0).normalize();
      cameraUp.setFromMatrixColumn(camera.matrixWorld, 1).normalize();
      const viewDistance = camera.position.distanceTo(cameraPan);
      const worldPerPixel = (
        2 * viewDistance * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2))
      ) / renderer.domElement.clientHeight;
      cameraPan.addScaledVector(cameraRight, -dx * worldPerPixel);
      cameraPan.addScaledVector(cameraUp, dy * worldPerPixel);
      cameraPanPixels.x += dx;
      cameraPanPixels.y += dy;
      renderer.domElement.classList.add("panning");
    }
    pointerStart.x = event.clientX;
    pointerStart.y = event.clientY;
    updateCamera();
  });
  renderer.domElement.addEventListener("pointerup", (event) => {
    if (pointerStart && !pointerStart.moved) selectFieldAtPointer(event);
    pointerStart = null;
    renderer.domElement.classList.remove("panning");
  });
  renderer.domElement.addEventListener("pointercancel", () => {
    pointerStart = null;
    renderer.domElement.classList.remove("panning");
  });
  renderer.domElement.addEventListener("wheel", (event) => {
    cameraView.radius = Math.max(
      5.5,
      Math.min(22, cameraView.radius + event.deltaY * 0.008),
    );
    updateCamera();
  }, { passive: true });
}

function resizeRenderer() {
  const width = elements.canvas.clientWidth;
  const height = elements.canvas.clientHeight;
  if (!width || !height) return;
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
  renderer.setSize(width, height, false);
}

function animate(now) {
  requestAnimationFrame(animate);
  const elapsed = Math.min(0.1, (now - lastFrame) / 1000);
  lastFrame = now;
  if (isAuthenticated && !session.running) {
    frameBudget += elapsed * TICKS_PER_SECOND * session.progression.speedMultiplier();
    const ticks = Math.min(100, Math.floor(frameBudget));
    frameBudget -= ticks;
    idleTicks += ticks;
    if (idleTicks >= 60) {
      const advance = idleTicks;
      idleTicks = 0;
      session.advanceIdle(advance);
      renderWorld();
    }
  }
  if (session) {
    pigDroneOrbitAngle = (pigDroneOrbitAngle + elapsed * PIG_DRONE_ORBIT_SPEED) % (Math.PI * 2);
    updatePigDronePosition(now);
    updateDronePosition(now);
    for (const [index, rotor] of droneRotors.entries()) {
      rotor.rotation.y = now * 0.018 * (index % 2 === 0 ? 1 : -1);
    }
    for (const [index, rotor] of pigDroneRotors.entries()) {
      rotor.rotation.y = now * 0.018 * (index % 2 === 0 ? -1 : 1);
    }
    updateCropGrowth();
    updateHarvestAnimations(now);
  }
  renderer.render(scene, camera);
}

async function main() {
  createResourceHud();
  const [entitiesRaw, costsRaw, techTreeRaw] = await Promise.all([
    fetch("../data/entities.json").then((response) => {
      if (!response.ok) throw new Error(`Could not load entities.json (${response.status}).`);
      return response.json();
    }),
    fetch("../data/costs.json").then((response) => {
      if (!response.ok) throw new Error(`Could not load costs.json (${response.status}).`);
      return response.json();
    }),
    fetch("../data/techtree.json").then((response) => {
      if (!response.ok) throw new Error(`Could not load techtree.json (${response.status}).`);
      return response.json();
    }),
  ]);
  const entityDefs = Object.fromEntries(
    Object.entries(entitiesRaw).filter(([name]) => !name.startsWith("_")),
  );
  const costs = Object.fromEntries(
    Object.entries(costsRaw).filter(([name]) => !name.startsWith("_")),
  );
  gameData = { entities: entityDefs, costs, techTree: techTreeRaw };
  setupEditor(elements.editorPanel, true);
  session = new GameSession(entityDefs, costs, techTreeRaw, () => {
    handleNewActions();
    updateHud();
    scheduleWorldRender();
  });
  renderWorld();
  elements.accountForm.addEventListener("submit", submitAccount);
  elements.developerToggle.addEventListener("click", openDeveloperPanel);
  elements.developerForm.addEventListener("submit", saveDeveloperResources);
  elements.developerCancel.addEventListener("click", closeDeveloperPanel);
  elements.accountMode.addEventListener("click", () => {
    setAccountMode(accountMode === "login" ? "register" : "login");
  });
  try {
    const accounts = readAccounts();
    setAccountMode(Object.keys(accounts).length ? "login" : "register");
  } catch (error) {
    elements.accountError.textContent = error.message;
  }
  $("#add-editor-button").addEventListener("click", () => addEditorWindow());
  elements.researchToggle.addEventListener("click", () => {
    setResearchMode(elements.research.classList.contains("hidden"));
  });
  setupResearchNavigation();
  setupGuideNavigation();
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      setResearchMode(false);
      elements.guide.classList.add("hidden");
      closeDeveloperPanel();
      if (!elements.closeEditorDialog.classList.contains("hidden")) dismissCloseEditor();
      if (!elements.scriptErrorDialog.classList.contains("hidden")) {
        elements.scriptErrorDialog.classList.add("hidden");
      }
    }
  });
  setupWindowPanels();
  setupCamera();
  renderWorld();
  resizeRenderer();
  window.addEventListener("resize", () => {
    resizeRenderer();
    resizeResearchView();
  });
  setEditorStatus(mainEditor, "READY");
  window.addEventListener("beforeunload", () => {
    if (session && isAuthenticated) {
      try {
        session.save(elements.code.value);
        saveEditorWindows();
      } catch (error) {
        console.error("Could not save game before closing.", error);
      }
    }
  });
  window.setInterval(saveProgress, 10000);
  requestAnimationFrame(animate);
}

main().catch((error) => {
  console.error(error);
  showScriptError(null, `Startup error: ${error.message}`);
  if (mainEditor) setEditorStatus(mainEditor, `ERROR · ${error.message}`, true);
});
