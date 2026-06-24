import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";

const viewerEl = document.getElementById("viewer");
const statusEl = document.getElementById("status");
const procEl = document.getElementById("proc");
const hintEl = document.getElementById("hint");
const overlay = document.getElementById("overlay");

// --- scene setup -------------------------------------------------------------
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0f1115);

const camera = new THREE.PerspectiveCamera(60, 1, 0.1, 1000);
camera.position.set(8, 8, 8);

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
viewerEl.appendChild(renderer.domElement);

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
scene.add(new THREE.GridHelper(60, 60, 0x2a2f3a, 0x1c2029));

const loader = new GLTFLoader();
const buildingGroup = new THREE.Group();
const furnitureGroup = new THREE.Group();
scene.add(buildingGroup, furnitureGroup);

let palette = [];
let lastDetection = null;

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

// --- ui helpers --------------------------------------------------------------
function setStatus(msg) { statusEl.textContent = msg; }
function proc(msg) { procEl.textContent = msg; procEl.classList.toggle("show", !!msg); }
function clearGroup(g) { while (g.children.length) g.remove(g.children[0]); }
function setStat(id, v) { document.getElementById(id).textContent = v; }

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

// --- pipeline ----------------------------------------------------------------
async function run(file) {
  if (!file || !file.type.startsWith("image/")) return setStatus("Please drop an image file (PNG/JPG).");
  hintEl.classList.add("hide");
  try {
    proc("① Detecting walls…");
    const fd = new FormData();
    fd.append("file", file);
    lastDetection = await fetch("/api/floorplan/detect", { method: "POST", body: fd }).then((r) => r.json());
    setStat("statWalls", lastDetection.walls.length);

    proc("② Building 3D model…");
    const gen = await fetch("/api/model/generate", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(withColors(lastDetection)),
    }).then((r) => r.json());
    await loadBuilding(gen.model_url);

    proc("③ Detecting rooms & furnishing…");
    await furnish();
    proc("");
  } catch (e) {
    proc("");
    setStatus(`Something went wrong: ${e}`);
  }
}

function loadBuilding(url) {
  return new Promise((resolve) => {
    loader.load(`${url}?t=${Date.now()}`, (gltf) => {
      clearGroup(buildingGroup);
      enableShadows(gltf.scene);
      buildingGroup.add(gltf.scene);
      frameObject(gltf.scene);
      resolve();
    }, undefined, (err) => { setStatus(`Failed to load model: ${err}`); resolve(); });
  });
}

// --- furniture ---------------------------------------------------------------
function placeholderBox(p) {
  const geo = new THREE.BoxGeometry(p.width, p.height, p.depth);
  const mat = new THREE.MeshStandardMaterial({ color: KIND_COLOR[p.kind] ?? 0x888888, roughness: 0.7 });
  const mesh = new THREE.Mesh(geo, mat);
  mesh.position.set(p.x, p.height / 2, p.z);
  mesh.rotation.y = p.rotation_y;
  enableShadows(mesh);
  return mesh;
}

function placeRealModel(p) {
  loader.load(p.model_url, (gltf) => {
    const obj = gltf.scene;
    const size = new THREE.Box3().setFromObject(obj).getSize(new THREE.Vector3());
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
    method: "POST", headers: { "Content-Type": "application/json" },
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

  setStat("statRooms", rooms.length);
  setStat("statItems", placements.length);
  setStat("statReal", real);
  document.getElementById("resultBox").style.display = "block";
  renderLegend(placements);
  setStatus(real
    ? `Done — ${real} real model(s) placed.`
    : "Done — placeholders shown. Add SKETCHFAB_API_TOKEN for real furniture.");
}

function renderLegend(placements) {
  const el = document.getElementById("legend");
  el.innerHTML = "";
  const kinds = [...new Set(placements.map((p) => p.kind))];
  for (const k of kinds) {
    const row = document.createElement("div");
    row.className = "row";
    const c = "#" + (KIND_COLOR[k] ?? 0x888888).toString(16).padStart(6, "0");
    row.innerHTML = `<span class="dot" style="background:${c}"></span> ${k}`;
    el.appendChild(row);
  }
}

// --- palette -> colors -------------------------------------------------------
function withColors(detection) {
  const body = { ...detection };
  if (palette.length) {
    body.wall_color = palette[palette.length - 1];
    body.floor_color = palette[Math.floor(palette.length / 2)];
  }
  return body;
}

// --- input: drag & drop + click ---------------------------------------------
const fileInput = document.getElementById("file");
const dropzone = document.getElementById("dropzone");

dropzone.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", () => fileInput.files[0] && run(fileInput.files[0]));

let dragDepth = 0; // ignore dragenter/leave bubbling from children
window.addEventListener("dragenter", (e) => { e.preventDefault(); if (dragDepth++ === 0) overlay.classList.add("show"); });
window.addEventListener("dragover", (e) => e.preventDefault());
window.addEventListener("dragleave", (e) => { e.preventDefault(); if (--dragDepth <= 0) { dragDepth = 0; overlay.classList.remove("show"); } });
window.addEventListener("drop", (e) => {
  e.preventDefault();
  dragDepth = 0; overlay.classList.remove("show");
  const file = e.dataTransfer?.files?.[0];
  if (file) run(file);
});

// --- palette button ----------------------------------------------------------
document.getElementById("paletteBtn").addEventListener("click", async () => {
  const query = document.getElementById("inspoQuery").value;
  setStatus("Fetching palette…");
  const res = await fetch(`/api/inspo/palette?query=${encodeURIComponent(query)}`);
  if (!res.ok) return setStatus(`Palette unavailable: ${(await res.json()).detail}`);
  palette = (await res.json()).palette;
  const el = document.getElementById("palette");
  el.innerHTML = "";
  for (const hex of palette) {
    const sw = document.createElement("div");
    sw.className = "swatch"; sw.style.background = hex; sw.title = hex;
    el.appendChild(sw);
  }
  if (lastDetection) {
    proc("Recoloring…");
    const gen = await fetch("/api/model/generate", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(withColors(lastDetection)),
    }).then((r) => r.json());
    await loadBuilding(gen.model_url);
    await furnish();
    proc("");
  } else {
    setStatus("Palette ready. Drop a floor plan to apply it.");
  }
});
