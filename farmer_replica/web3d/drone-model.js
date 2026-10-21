import * as THREE from "three";

const materials = {
  shell: new THREE.MeshStandardMaterial({
    color: "#aeb8b8",
    flatShading: true,
    metalness: 0.12,
    roughness: 0.76,
  }),
  frame: new THREE.MeshStandardMaterial({
    color: "#778283",
    flatShading: true,
    metalness: 0.16,
    roughness: 0.72,
  }),
  motor: new THREE.MeshStandardMaterial({
    color: "#626e70",
    flatShading: true,
    metalness: 0.18,
    roughness: 0.68,
  }),
  blade: new THREE.MeshStandardMaterial({
    color: "#d0d5d2",
    flatShading: true,
    side: THREE.DoubleSide,
    roughness: 0.82,
  }),
  lens: new THREE.MeshStandardMaterial({
    color: "#8bc2c8",
    emissive: "#234c50",
    flatShading: true,
    roughness: 0.38,
  }),
};

function addCylinderBetween(parent, start, end, radiusStart, radiusEnd, material, segments = 7) {
  const from = new THREE.Vector3(...start);
  const to = new THREE.Vector3(...end);
  const direction = to.clone().sub(from);
  const mesh = new THREE.Mesh(
    new THREE.CylinderGeometry(radiusEnd, radiusStart, direction.length(), segments),
    material,
  );
  mesh.position.copy(from).add(to).multiplyScalar(0.5);
  mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), direction.normalize());
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  parent.add(mesh);
  return mesh;
}

function makeBladeGeometry() {
  const shape = new THREE.Shape();
  shape.moveTo(0.025, -0.025);
  shape.lineTo(0.245, -0.045);
  shape.lineTo(0.36, -0.022);
  shape.lineTo(0.385, 0.025);
  shape.lineTo(0.115, 0.044);
  shape.lineTo(0.015, 0.025);
  shape.closePath();
  const geometry = new THREE.ShapeGeometry(shape);
  geometry.rotateX(-Math.PI / 2);
  return geometry;
}

export function createLowPolyDrone() {
  const body = new THREE.Group();
  body.name = "low-poly-drone-body";

  const hull = new THREE.Mesh(new THREE.IcosahedronGeometry(1, 1), materials.shell);
  hull.name = "faceted-drone-hull";
  hull.scale.set(0.3, 0.14, 0.245);
  hull.castShadow = true;
  hull.receiveShadow = true;
  body.add(hull);

  const battery = new THREE.Mesh(
    new THREE.BoxGeometry(0.29, 0.075, 0.2),
    materials.frame,
  );
  battery.position.set(0, -0.105, -0.015);
  battery.castShadow = true;
  body.add(battery);

  const camera = new THREE.Mesh(
    new THREE.IcosahedronGeometry(0.055, 0),
    materials.lens,
  );
  camera.name = "drone-camera";
  camera.position.set(0, -0.015, 0.225);
  camera.scale.set(1, 0.78, 0.72);
  body.add(camera);

  const rotors = [];
  const bladeGeometry = makeBladeGeometry();
  const signs = [-1, 1];
  for (const xSign of signs) {
    for (const zSign of signs) {
      const armStart = [xSign * 0.12, 0.015, zSign * 0.105];
      const motorPosition = [xSign * 0.46, 0.015, zSign * 0.43];
      addCylinderBetween(
        body,
        armStart,
        motorPosition,
        0.075,
        0.052,
        materials.frame,
      );

      const motor = new THREE.Mesh(
        new THREE.CylinderGeometry(0.085, 0.095, 0.105, 8),
        materials.motor,
      );
      motor.position.set(motorPosition[0], 0.055, motorPosition[2]);
      motor.castShadow = true;
      body.add(motor);

      const rotor = new THREE.Group();
      rotor.name = "drone-rotor";
      rotor.position.set(motorPosition[0], 0.115, motorPosition[2]);
      for (const rotation of [0, Math.PI]) {
        const blade = new THREE.Mesh(bladeGeometry, materials.blade);
        blade.rotation.y = rotation;
        blade.castShadow = true;
        rotor.add(blade);
      }
      const cap = new THREE.Mesh(
        new THREE.CylinderGeometry(0.035, 0.045, 0.045, 7),
        materials.frame,
      );
      cap.position.y = 0.018;
      rotor.add(cap);
      body.add(rotor);
      rotors.push(rotor);
    }
  }

  for (const zSign of signs) {
    const railZ = zSign * 0.145;
    addCylinderBetween(
      body,
      [-0.235, -0.255, railZ],
      [0.235, -0.255, railZ],
      0.027,
      0.027,
      materials.motor,
      6,
    );
    for (const xSign of signs) {
      addCylinderBetween(
        body,
        [xSign * 0.12, -0.075, zSign * 0.095],
        [xSign * 0.19, -0.245, railZ],
        0.035,
        0.026,
        materials.frame,
        6,
      );
    }
  }

  return { body, rotors };
}

export function createLowPolyPigDrone() {
  const body = new THREE.Group();
  body.name = "low-poly-pig-drone-body";

  const pigShell = new THREE.MeshStandardMaterial({
    color: "#e98e9d",
    flatShading: true,
    roughness: 0.78,
  });
  const pigLight = new THREE.MeshStandardMaterial({
    color: "#f5b0b6",
    flatShading: true,
    roughness: 0.78,
  });
  const nostrilMaterial = new THREE.MeshStandardMaterial({
    color: "#713b48",
    flatShading: true,
    roughness: 0.85,
  });
  const pigEyeMaterial = new THREE.MeshStandardMaterial({
    color: "#382d33",
    roughness: 0.55,
  });
  const slotMaterial = new THREE.MeshStandardMaterial({
    color: "#633d45",
    roughness: 0.85,
  });

  const torso = new THREE.Mesh(new THREE.IcosahedronGeometry(1, 1), pigShell);
  torso.name = "piggy-bank-body";
  torso.scale.set(0.34, 0.25, 0.4);
  torso.castShadow = true;
  torso.receiveShadow = true;
  body.add(torso);

  const snout = new THREE.Mesh(
    new THREE.CylinderGeometry(0.105, 0.12, 0.12, 8),
    pigLight,
  );
  snout.name = "pig-snout";
  snout.rotation.x = Math.PI / 2;
  snout.position.set(0, -0.015, 0.385);
  snout.castShadow = true;
  body.add(snout);

  for (const side of [-1, 1]) {
    const nostril = new THREE.Mesh(
      new THREE.SphereGeometry(0.025, 6, 5),
      nostrilMaterial,
    );
    nostril.position.set(side * 0.048, 0.015, 0.449);
    nostril.scale.set(0.8, 1, 0.45);
    body.add(nostril);

    const eye = new THREE.Mesh(
      new THREE.SphereGeometry(0.032, 7, 6),
      pigEyeMaterial,
    );
    eye.position.set(side * 0.225, 0.105, 0.23);
    body.add(eye);

    const ear = new THREE.Mesh(
      new THREE.ConeGeometry(0.09, 0.2, 5),
      pigShell,
    );
    ear.name = "pig-ear";
    ear.position.set(side * 0.21, 0.265, 0.16);
    ear.rotation.z = side * -0.32;
    ear.rotation.x = -0.18;
    ear.castShadow = true;
    body.add(ear);

    const leg = new THREE.Mesh(
      new THREE.CylinderGeometry(0.055, 0.045, 0.16, 6),
      pigLight,
    );
    leg.position.set(side * 0.2, -0.235, 0.17);
    leg.castShadow = true;
    body.add(leg);

    const rearLeg = leg.clone();
    rearLeg.position.z = -0.17;
    body.add(rearLeg);
  }

  const coinSlot = new THREE.Mesh(
    new THREE.BoxGeometry(0.14, 0.018, 0.045),
    slotMaterial,
  );
  coinSlot.name = "piggy-bank-coin-slot";
  coinSlot.position.set(0, 0.245, -0.045);
  body.add(coinSlot);

  const rotors = [];
  const bladeGeometry = makeBladeGeometry();
  const rotorArmMaterial = materials.frame;
  const signs = [-1, 1];
  for (const xSign of signs) {
    for (const zSign of signs) {
      const armStart = [xSign * 0.13, 0.045, zSign * 0.14];
      const motorPosition = [xSign * 0.49, 0.045, zSign * 0.46];
      addCylinderBetween(
        body,
        armStart,
        motorPosition,
        0.07,
        0.05,
        rotorArmMaterial,
      );

      const motor = new THREE.Mesh(
        new THREE.CylinderGeometry(0.082, 0.092, 0.1, 8),
        materials.motor,
      );
      motor.position.set(motorPosition[0], 0.085, motorPosition[2]);
      motor.castShadow = true;
      body.add(motor);

      const rotor = new THREE.Group();
      rotor.name = "pig-drone-rotor";
      rotor.position.set(motorPosition[0], 0.14, motorPosition[2]);
      for (const rotation of [0, Math.PI]) {
        const blade = new THREE.Mesh(bladeGeometry, materials.blade);
        blade.rotation.y = rotation;
        blade.castShadow = true;
        rotor.add(blade);
      }
      const cap = new THREE.Mesh(
        new THREE.CylinderGeometry(0.035, 0.045, 0.045, 7),
        materials.frame,
      );
      cap.position.y = 0.018;
      rotor.add(cap);
      body.add(rotor);
      rotors.push(rotor);
    }
  }

  return { body, rotors };
}

function createFoliageMaterial(color) {
  return new THREE.MeshStandardMaterial({
    color,
    flatShading: true,
    roughness: 0.9,
    side: THREE.DoubleSide,
  });
}

export function createLowPolyBush() {
  const bush = new THREE.Group();
  bush.name = "low-poly-bush";
  const shades = ["#319c4f", "#36a653", "#2b9147", "#40aa59", "#278642"];
  const clusters = [
    { position: [0, 0.27, 0], scale: [0.29, 0.3, 0.28] },
    { position: [-0.22, 0.16, 0.015], scale: [0.235, 0.22, 0.24] },
    { position: [0.22, 0.16, 0], scale: [0.235, 0.22, 0.24] },
    { position: [0, 0.15, 0.21], scale: [0.245, 0.22, 0.22] },
    { position: [0, 0.15, -0.21], scale: [0.245, 0.22, 0.22] },
    { position: [-0.12, 0.12, -0.15], scale: [0.21, 0.19, 0.22] },
    { position: [0.13, 0.12, 0.15], scale: [0.21, 0.19, 0.22] },
  ];

  clusters.forEach((cluster, index) => {
    const foliage = new THREE.Mesh(
      new THREE.IcosahedronGeometry(1, 1),
      createFoliageMaterial(shades[index % shades.length]),
    );
    foliage.position.set(...cluster.position);
    foliage.scale.set(...cluster.scale);
    foliage.castShadow = true;
    foliage.receiveShadow = true;
    bush.add(foliage);
  });

  return bush;
}

function createGrassBladeGeometry(height, width, bendX, bendZ) {
  const geometry = new THREE.BufferGeometry();
  const middleY = height * 0.56;
  const vertices = new Float32Array([
    -width * 0.5, 0, 0,
    width * 0.5, 0, 0,
    bendX * 0.42 + width * 0.22, middleY, bendZ * 0.42,
    bendX, height, bendZ,
    bendX * 0.42 - width * 0.22, middleY, bendZ * 0.42,
  ]);
  geometry.setAttribute("position", new THREE.BufferAttribute(vertices, 3));
  geometry.setIndex([0, 1, 2, 0, 2, 3, 0, 3, 4]);
  geometry.computeVertexNormals();
  return geometry;
}

export function createLowPolyGrass(seed = 0) {
  const grass = new THREE.Group();
  grass.name = "low-poly-grass";
  const shades = ["#247b35", "#2d8c3d", "#369847", "#1e7130"];
  let value = (seed + 1) * 0x45d9f3b;
  const next = () => {
    value = (value * 1664525 + 1013904223) >>> 0;
    return value / 0x100000000;
  };

  for (let index = 0; index < 17; index += 1) {
    const angle = next() * Math.PI * 2;
    const radius = Math.sqrt(next()) * 0.17;
    const height = 0.42 + next() * 0.34;
    const width = 0.035 + next() * 0.025;
    const bend = 0.035 + next() * 0.1;
    const blade = new THREE.Mesh(
      createGrassBladeGeometry(height, width, Math.cos(angle) * bend, Math.sin(angle) * bend),
      createFoliageMaterial(shades[index % shades.length]),
    );
    blade.position.set(Math.cos(angle) * radius, 0, Math.sin(angle) * radius);
    blade.rotation.y = angle * 0.35;
    blade.castShadow = true;
    grass.add(blade);
  }

  return grass;
}

export function createLowPolyFieldTile(seed = 0) {
  const tile = new THREE.Group();
  tile.name = "low-poly-field-tile";
  const baseMaterial = new THREE.MeshStandardMaterial({
    color: "#765238",
    flatShading: true,
    roughness: 1,
  });
  const turfMaterial = new THREE.MeshStandardMaterial({
    color: seed % 3 === 0 ? "#718f49" : "#78964c",
    flatShading: true,
    roughness: 1,
  });
  const tilledMaterial = new THREE.MeshStandardMaterial({
    color: "#65472f",
    flatShading: true,
    roughness: 1,
  });
  const furrowMaterial = new THREE.MeshStandardMaterial({
    color: "#765237",
    flatShading: true,
    roughness: 1,
  });

  let randomValue = (seed + 11) * 0x45d9f3b;
  const random = () => {
    randomValue = (randomValue * 1664525 + 1013904223) >>> 0;
    return randomValue / 0x100000000;
  };
  const addBlock = (name, position, size, material, castShadow = true) => {
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(...size), material);
    mesh.name = name;
    mesh.position.set(...position);
    mesh.castShadow = castShadow;
    mesh.receiveShadow = true;
    tile.add(mesh);
    return mesh;
  };

  addBlock("earth-core", [0, -0.115, 0], [0.98, 0.23, 0.98], baseMaterial);
  addBlock(
    "dark-earth-seam",
    [0, -0.19, 0],
    [0.985, 0.045, 0.985],
    tilledMaterial,
  );

  const turfTop = addBlock(
    "thin-grass-topsoil",
    [0, 0.013, 0],
    [0.98, 0.036, 0.98],
    turfMaterial,
    false,
  );
  const tilledTop = addBlock(
    "tilled-soil-surface",
    [0, 0.013, 0],
    [0.98, 0.036, 0.98],
    tilledMaterial,
    false,
  );
  tilledTop.visible = false;

  for (let index = 0; index < 3; index += 1) {
    const furrow = addBlock(
      `soil-furrow-${index}`,
      [-0.28 + index * 0.28, 0.035, 0],
      [0.045, 0.012, 0.72],
      furrowMaterial,
      false,
    );
    furrow.visible = false;
  }

  const rockMaterials = ["#797872", "#8d8980", "#686b66"].map((color) =>
    new THREE.MeshStandardMaterial({
      color,
      flatShading: true,
      roughness: 1,
    }),
  );
  const rockGeometry = new THREE.IcosahedronGeometry(1, 0);
  for (let index = 0; index < 10; index += 1) {
    const side = index % 4;
    const offset = -0.37 + random() * 0.74;
    const x = side < 2 ? (side === 0 ? -0.465 : 0.465) : offset;
    const z = side < 2 ? offset : (side === 2 ? -0.465 : 0.465);
    const rock = new THREE.Mesh(rockGeometry, rockMaterials[index % rockMaterials.length]);
    const size = 0.028 + random() * 0.035;
    rock.name = "embedded-field-stone";
    rock.position.set(x, -0.115 + random() * 0.105, z);
    rock.scale.set(size * (0.9 + random() * 0.8), size * 0.7, size);
    rock.rotation.set(random() * 0.6, random() * Math.PI, random() * 0.6);
    rock.castShadow = true;
    rock.receiveShadow = true;
    tile.add(rock);
  }

  const turfBlades = [];
  const grassMaterials = ["#52783b", "#638743", "#78964c"].map((color) =>
    new THREE.MeshStandardMaterial({
      color,
      flatShading: true,
      side: THREE.DoubleSide,
      roughness: 1,
    }),
  );
  for (let index = 0; index < 8; index += 1) {
    const angle = random() * Math.PI * 2;
    const radius = 0.33 + random() * 0.12;
    const height = 0.045 + random() * 0.045;
    const blade = new THREE.Mesh(
      createGrassBladeGeometry(height, 0.018 + random() * 0.012, Math.cos(angle) * 0.018, Math.sin(angle) * 0.018),
      grassMaterials[index % grassMaterials.length],
    );
    blade.position.set(Math.cos(angle) * radius, 0.031, Math.sin(angle) * radius);
    blade.rotation.y = angle;
    blade.name = "turf-edge-blade";
    blade.castShadow = true;
    tile.add(blade);
    turfBlades.push(blade);
  }

  const setGround = (ground) => {
    const isSoil = ground === "soil";
    turfTop.visible = !isSoil;
    for (const blade of turfBlades) blade.visible = !isSoil;
    tilledTop.visible = isSoil;
    for (const furrow of tile.children) {
      if (furrow.name.startsWith("soil-furrow-")) furrow.visible = isSoil;
    }
    return isSoil ? tilledTop : turfTop;
  };

  return { group: tile, setGround };
}
