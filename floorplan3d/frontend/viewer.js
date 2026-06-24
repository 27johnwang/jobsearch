import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";

const viewerEl = document.getElementById("viewer");
const statusEl = document.getElementById("status");

// --- scene setup -------------------------------------------------------------
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x1a1a1f);

const camera = new THREE.PerspectiveCamera(60, 1, 0.1, 1000);
camera.position.set(8, 8, 8);

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
viewerEl.appendChild(renderer.domElement);

// Image-based lighting for believable PBR surfaces.
const pmrem = new THREE.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;

scene.add(new THREE.HemisphereLight(0xffffff, 0x444444, 0.6));
const dir = new THREE.DirectionalLight(0xffffff, 2.0);
dir.position.set(12, 24, 8);
dir.castShadow = true;
dir.shadow.mapSize.set(2048, 2048);
Object.assign(dir.shadow.camera, { left: -30, right: 30, top: 30, bottom: -30, near: 1, far: 80 });
scene.add(dir);
scene.add(new THREE.GridHelper(60, 60, 0x444444, 0x222222));

const loader = new GLTFLoader();
const buildingGroup = new THREE.Group();   // walls + floor
const furnitureGroup = new THREE.Group();   // placed items
scene.add(buildingGroup, furnitureGroup);

let palette = [];           // hex strings from Unsplash
let lastDetection = null;   // detection JSON, reused for furnishing

const KIND_COLOR = {
  bedroom: 0x6a8cc7, living: 0xc77f5a, dining: 0x8a9a5b,
  kitchen: 0xb0b0b0, bathroom: 0x6fb1c4, office: 0xc4a26f,
};

function resize() {
  const { clientWidth: w, clientHeight: h } = viewerEl;
  renderer.setSize(w, h);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}
window.addEventListener("resize", resize);
resize();

(function animate() {
  requestAnimationFrame(animate);
  controls.update();
  renderer.render(scene, camera);
})();

function setStatus(msg) { statusEl.textContent = msg; }
function clearGroup(g) { while (g.children.length) g.remove(g.children[0]); }

function enableShadows(obj, { cast = true, receive = true } = {}) {
  obj.traverse((c) => { if (c.isMesh) { c.castShadow = cast; c.receiveShadow = receive; } });
}

function frameObject(obj) {
  const box = new THREE.Box3().setFromObject(obj);
  if (box.isEmpty()) return;
  const center = box.getCenter(new THREE.Vector3());
  const size = box.getSize(new THREE.Vector3()).length();
  controls.target.copy(center);
  camera.position.copy(center).add(new THREE.Vector3(size, size * 0.8, size));
  camera.near = size / 100;
  camera.far = size * 10;
  camera.updateProjectionMatrix();
}

function loadBuilding(url) {
  loader.load(`${url}?t=${Date.now()}`, (gltf) => {
    clearGroup(buildingGroup);
    enableShadows(gltf.scene);
    buildingGroup.add(gltf.scene);
    frameObject(gltf.scene);
    setStatus("3D model loaded. Furnishing…");
  }, undefined, (err) => setStatus(`Failed to load model: ${err}`));
}

// --- furniture ---------------------------------------------------------------
function placeholderBox(p) {
  const geo = new THREE.BoxGeometry(p.width, p.height, p.depth);
  const mat = new THREE.MeshStandardMaterial({
    color: KIND_COLOR[p.kind] ?? 0x888888, roughness: 0.7,
  });
  const mesh = new THREE.Mesh(geo, mat);
  mesh.position.set(p.x, p.height / 2, p.z);
  mesh.rotation.y = p.rotation_y;
  enableShadows(mesh);
  return mesh;
}

function placeRealModel(p) {
  loader.load(p.model_url, (gltf) => {
    const obj = gltf.scene;
    // Scale the asset's bounding box to the planned footprint.
    const bb = new THREE.Box3().setFromObject(obj);
    const size = bb.getSize(new THREE.Vector3());
    const s = Math.min(p.width / (size.x || 1), p.depth / (size.z || 1), p.height / (size.y || 1));
    obj.scale.setScalar(s);
    obj.position.set(p.x, 0, p.z);
    obj.rotation.y = p.rotation_y;
    enableShadows(obj);
    furnitureGroup.add(obj);
  }, undefined, () => furnitureGroup.add(placeholderBox(p)));
}

async function furnish() {
  if (!lastDetection) return;
  const res = await fetch("/api/furniture/plan", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(withColors(lastDetection)),
  });
  if (!res.ok) return setStatus(`Furnishing failed: ${(await res.json()).detail}`);
  const { rooms, placements } = await res.json();

  clearGroup(furnitureGroup);
  let real = 0;
  for (const p of placements) {
    if (p.model_url) { placeRealModel(p); real++; }
    else furnitureGroup.add(placeholderBox(p));
  }
  setStatus(
    `${rooms.length} room(s), ${placements.length} item(s) placed` +
    (real ? ` (${real} real model(s))` : " (placeholders — add SKETCHFAB_API_TOKEN for real models)")
  );
}

// --- palette -> colors -------------------------------------------------------
function withColors(detection) {
  const body = { ...detection };
  if (palette.length) {
    body.wall_color = palette[palette.length - 1]; // lightest-ish tone for walls
    body.floor_color = palette[Math.floor(palette.length / 2)];
  }
  return body;
}

// --- pipeline wiring ---------------------------------------------------------
document.getElementById("detectBtn").addEventListener("click", async () => {
  const file = document.getElementById("file").files[0];
  if (!file) return setStatus("Pick a floor-plan image first.");

  setStatus("Detecting walls…");
  const fd = new FormData();
  fd.append("file", file);
  lastDetection = await fetch("/api/floorplan/detect", { method: "POST", body: fd }).then((r) => r.json());
  setStatus(`Detected ${lastDetection.walls.length} wall(s). Building 3D…`);

  const gen = await fetch("/api/model/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(withColors(lastDetection)),
  }).then((r) => r.json());

  loadBuilding(gen.model_url);
  await furnish();
});

document.getElementById("paletteBtn").addEventListener("click", async () => {
  const query = document.getElementById("inspoQuery").value;
  setStatus("Fetching palette…");
  const res = await fetch(`/api/inspo/palette?query=${encodeURIComponent(query)}`);
  if (!res.ok) return setStatus(`Palette unavailable: ${(await res.json()).detail}`);
  const data = await res.json();
  palette = data.palette;
  const el = document.getElementById("palette");
  el.innerHTML = "";
  for (const hex of palette) {
    const sw = document.createElement("div");
    sw.className = "swatch";
    sw.style.background = hex;
    sw.title = hex;
    el.appendChild(sw);
  }
  setStatus(`Palette for "${query}" ready. Rebuild to apply it to walls/floor.`);
});
