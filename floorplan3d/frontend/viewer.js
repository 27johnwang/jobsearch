import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";

const viewerEl = document.getElementById("viewer");
const statusEl = document.getElementById("status");

// --- scene setup -------------------------------------------------------------
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x1a1a1f);

const camera = new THREE.PerspectiveCamera(60, 1, 0.1, 1000);
camera.position.set(8, 8, 8);

const renderer = new THREE.WebGLRenderer({ antialias: true });
viewerEl.appendChild(renderer.domElement);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;

scene.add(new THREE.HemisphereLight(0xffffff, 0x444444, 1.2));
const dir = new THREE.DirectionalLight(0xffffff, 1.0);
dir.position.set(10, 20, 10);
scene.add(dir);
scene.add(new THREE.GridHelper(40, 40, 0x444444, 0x222222));

const loader = new GLTFLoader();
let current = null;

function resize() {
  const { clientWidth: w, clientHeight: h } = viewerEl;
  renderer.setSize(w, h);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}
window.addEventListener("resize", resize);
resize();

function animate() {
  requestAnimationFrame(animate);
  controls.update();
  renderer.render(scene, camera);
}
animate();

function loadModel(url) {
  loader.load(
    `${url}?t=${Date.now()}`, // bust cache; latest.glb is overwritten
    (gltf) => {
      if (current) scene.remove(current);
      current = gltf.scene;
      scene.add(current);
      frameObject(current);
      setStatus("3D model loaded. Drag to orbit, scroll to zoom.");
    },
    undefined,
    (err) => setStatus(`Failed to load model: ${err}`)
  );
}

function frameObject(obj) {
  const box = new THREE.Box3().setFromObject(obj);
  const center = box.getCenter(new THREE.Vector3());
  const size = box.getSize(new THREE.Vector3()).length();
  controls.target.copy(center);
  camera.position.copy(center).add(new THREE.Vector3(size, size, size));
  camera.near = size / 100;
  camera.far = size * 10;
  camera.updateProjectionMatrix();
}

function setStatus(msg) {
  statusEl.textContent = msg;
}

// --- pipeline wiring ---------------------------------------------------------
document.getElementById("detectBtn").addEventListener("click", async () => {
  const file = document.getElementById("file").files[0];
  if (!file) return setStatus("Pick a floor-plan image first.");

  setStatus("Detecting walls…");
  const fd = new FormData();
  fd.append("file", file);
  const det = await fetch("/api/floorplan/detect", { method: "POST", body: fd }).then((r) => r.json());
  setStatus(`Detected ${det.walls.length} wall segments. Building 3D…`);

  const gen = await fetch("/api/model/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(det),
  }).then((r) => r.json());

  loadModel(gen.model_url);
});

document.getElementById("paletteBtn").addEventListener("click", async () => {
  const query = document.getElementById("inspoQuery").value;
  setStatus("Fetching palette…");
  const res = await fetch(`/api/inspo/palette?query=${encodeURIComponent(query)}`);
  if (!res.ok) return setStatus(`Palette unavailable: ${(await res.json()).detail}`);
  const data = await res.json();
  const el = document.getElementById("palette");
  el.innerHTML = "";
  for (const hex of data.palette) {
    const sw = document.createElement("div");
    sw.className = "swatch";
    sw.style.background = hex;
    sw.title = hex;
    el.appendChild(sw);
  }
  setStatus(`Palette for "${query}" ready.`);
});
