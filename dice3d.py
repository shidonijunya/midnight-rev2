"""Palco 3D de dados para o painel (Three.js via CDN, sem arquivos locais).

O Python calcula os resultados; este módulo só os *apresenta*. A animação termina
exatamente na face que corresponde ao valor recebido em `values`.

Uso:
    spec = build_spec(roll_id, caption, [{"label": "Rolagem", "sides": 20, "values": [14]}],
                      total=17, note=None)
    html = stage_html(spec, height=250)
"""
import json

THREE_URL = "https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"
MAX_DICE_3D = 12  # limite visual (meshes); a soma sempre usa todos os dados
SUPPORTED_SIDES = (4, 6, 8, 10, 12, 20, 100)
PALETTE = {4: "#d6455d", 6: "#3f7cf4", 8: "#2f9e62", 10: "#d9962b",
           12: "#9a5cf0", 20: "#6d4aff", 100: "#cf3f8d"}


def _face_labels(sides, value):
    """Rótulos das faces de um dado e o rótulo que deve ficar voltado para a câmera."""
    if sides == 100:  # d100 = dado de dezenas (00..90) + dado de unidades (0..9)
        tens_labels = ["00", "10", "20", "30", "40", "50", "60", "70", "80", "90"]
        unit_labels = [str(i) for i in range(10)]
        if value == 100:
            tens, unit = "00", "0"
        else:
            tens = "00" if value < 10 else str((value // 10) * 10)
            unit = str(value % 10)
        return [
            {"sides": 10, "labels": tens_labels, "target": tens, "color": PALETTE[100], "tag": "dezenas"},
            {"sides": 10, "labels": unit_labels, "target": unit, "color": PALETTE[100], "tag": "unidades"},
        ]
    labels = [str(i) for i in range(1, sides + 1)]
    return [{"sides": sides, "labels": labels, "target": str(value), "color": PALETTE.get(sides, "#6d4aff"), "tag": ""}]


def build_spec(roll_id, caption, groups, total=None, note=None, idle=False, totals=None):
    """Monta o JSON consumido pelo JavaScript.

    groups: lista de {"label": str, "sides": int, "values": [int, ...]}
    totals: lista opcional de {"label": str, "value": int|str} (ex.: Teste e Dano);
            se omitida e `total` for dado, vira [{"label": "Total", "value": total}].
    """
    if totals is None and total is not None:
        totals = [{"label": "Total", "value": total}]
    totals = [{"label": str(t["label"]), "value": t["value"]} for t in (totals or [])]
    dice = []
    hidden = 0
    clean_groups = []
    for g in groups:
        sides = int(g["sides"])
        values = [int(v) for v in g["values"]]
        clean_groups.append({"label": str(g.get("label", "")), "sides": sides,
                             "values": values[:40], "extra": max(0, len(values) - 40),
                             "color": PALETTE.get(sides, "#6d4aff")})
        for v in values:
            for die in _face_labels(sides, v):
                if len(dice) < MAX_DICE_3D:
                    die = dict(die)
                    die["group"] = str(g.get("label", ""))
                    dice.append(die)
                else:
                    hidden += 1
    if hidden:
        extra = f"3D mostra {MAX_DICE_3D} dados; a soma usa todos os dados rolados."
        note = f"{note} {extra}".strip() if note else extra
    return {"id": str(roll_id), "caption": str(caption or ""), "dice": dice, "groups": clean_groups,
            "totals": totals, "note": note, "idle": bool(idle)}


def idle_spec():
    return build_spec("idle", "Pronto para rolar", [{"label": "", "sides": 20, "values": [20]}], idle=True)


def _json_for_script(obj):
    text = json.dumps(obj, ensure_ascii=False)
    # evita fechar a tag <script> por engano e quebras de linha unicode
    return text.replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


JS = r"""
(function () {
"use strict";
var SPEC = __SPEC__;
var HEIGHT = __HEIGHT__;
var stage = document.getElementById("stage");
var hudCaption = document.getElementById("cap");
var hudFoot = document.getElementById("foot");
var hudNote = document.getElementById("note");
var fallback = document.getElementById("fallback");

/* ---------- utilidades de geometria (testáveis em Node) ---------- */
function flatten(geo) {
  var g = geo.index ? geo.toNonIndexed() : geo;
  g.computeVertexNormals();
  return g;
}

function d10Geometry() {
  var k = 0.2, c36 = Math.cos(Math.PI / 5), s36 = Math.sin(Math.PI / 5);
  var c72 = Math.cos(2 * Math.PI / 5), s72 = Math.sin(2 * Math.PI / 5);
  function det(h) {  // coplanaridade do papagaio [T, U0, L0, U1]
    var A = [1, k - h, 0], B = [c72, k - h, s72], C = [c36, -k - h, s36];
    return A[0] * (B[1] * C[2] - B[2] * C[1]) - A[1] * (B[0] * C[2] - B[2] * C[0]) + A[2] * (B[0] * C[1] - B[1] * C[0]);
  }
  var d0 = det(0), d1 = det(1);
  var h = -d0 / (d1 - d0);
  function ring(i, y, off) {
    var a = (2 * Math.PI / 5) * i + off;
    return new THREE.Vector3(Math.cos(a), y, Math.sin(a));
  }
  var T = new THREE.Vector3(0, h, 0), B = new THREE.Vector3(0, -h, 0);
  var tris = [];
  function addQuad(p) {
    var cen = new THREE.Vector3();
    p.forEach(function (v) { cen.add(v); });
    cen.divideScalar(p.length);
    var n = new THREE.Vector3().subVectors(p[1], p[0]).cross(new THREE.Vector3().subVectors(p[2], p[0]));
    if (n.dot(cen) < 0) p = p.slice().reverse();
    for (var i = 1; i < p.length - 1; i++) tris.push(p[0], p[i], p[i + 1]);
  }
  for (var i = 0; i < 5; i++) {
    var U0 = ring(i, k, 0), U1 = ring(i + 1, k, 0);
    var L0 = ring(i, -k, Math.PI / 5), L1 = ring(i + 1, -k, Math.PI / 5);
    addQuad([T, U0, L0, U1]);
    addQuad([B, L0, U1, L1]);
  }
  var arr = new Float32Array(tris.length * 3);
  tris.forEach(function (v, idx) { arr[idx * 3] = v.x; arr[idx * 3 + 1] = v.y; arr[idx * 3 + 2] = v.z; });
  var geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(arr, 3));
  geo.computeVertexNormals();
  var scale = 1.15 / Math.max(h, 1);
  geo.scale(scale, scale, scale);
  return geo;
}

function makeGeometry(sides) {
  switch (sides) {
    case 4: return new THREE.TetrahedronGeometry(1.3, 0);
    case 6: return new THREE.BoxGeometry(1.55, 1.55, 1.55);
    case 8: return new THREE.OctahedronGeometry(1.25, 0);
    case 10: return d10Geometry();
    case 12: return new THREE.DodecahedronGeometry(1.15, 0);
    default: return new THREE.IcosahedronGeometry(1.2, 0);
  }
}

function clusterFaces(geo) {
  var pos = geo.attributes.position, faces = [];
  var a = new THREE.Vector3(), b = new THREE.Vector3(), c = new THREE.Vector3();
  for (var i = 0; i < pos.count; i += 3) {
    a.fromBufferAttribute(pos, i); b.fromBufferAttribute(pos, i + 1); c.fromBufferAttribute(pos, i + 2);
    var cr = new THREE.Vector3().subVectors(b, a).cross(new THREE.Vector3().subVectors(c, a));
    var area = cr.length() / 2;
    if (area < 1e-9) continue;
    var n = cr.clone().normalize();
    var cen = a.clone().add(b).add(c).divideScalar(3);
    var f = null;
    for (var j = 0; j < faces.length; j++) { if (faces[j].normal.dot(n) > 0.9995) { f = faces[j]; break; } }
    if (!f) { f = { normal: n.clone(), center: new THREE.Vector3(), area: 0 }; faces.push(f); }
    f.center.addScaledVector(cen, area);
    f.area += area;
  }
  faces.forEach(function (f) {
    f.center.divideScalar(f.area);
    var up = new THREE.Vector3(0, 1, 0);
    up.addScaledVector(f.normal, -up.dot(f.normal));
    if (up.length() < 0.2) {
      up = new THREE.Vector3(0, 0, 1);
      up.addScaledVector(f.normal, -up.dot(f.normal));
    }
    f.up = up.normalize();
    f.right = new THREE.Vector3().crossVectors(f.up, f.normal).normalize();
  });
  return faces;
}

function assignLabels(faces, labels) {
  var N = faces.length, res = new Array(N), used = new Array(N), m = 0, i, j;
  for (i = 0; i < N; i++) { res[i] = null; used[i] = false; }
  for (i = 0; i < N; i++) {
    if (used[i]) continue;
    used[i] = true; res[i] = labels[m];
    for (j = i + 1; j < N; j++) {
      if (!used[j] && faces[j].normal.dot(faces[i].normal) < -0.98) { used[j] = true; res[j] = labels[N - 1 - m]; break; }
    }
    m++;
  }
  return res;
}

var TILT = new THREE.Quaternion().setFromEuler(new THREE.Euler(-0.32, 0.38, 0));

function finalQuaternion(face) {
  var M = new THREE.Matrix4().makeBasis(face.right, face.up, face.normal);
  var q = new THREE.Quaternion().setFromRotationMatrix(M).invert();
  return TILT.clone().multiply(q);
}

var texCache = {};
function labelTexture(text) {
  if (texCache[text]) return texCache[text];
  var cv = document.createElement("canvas"); cv.width = 128; cv.height = 128;
  var g = cv.getContext("2d");
  g.clearRect(0, 0, 128, 128);
  g.textAlign = "center"; g.textBaseline = "middle";
  g.font = "bold " + (text.length > 1 ? 60 : 80) + "px Arial, Helvetica, sans-serif";
  g.lineWidth = 9; g.strokeStyle = "rgba(0,0,0,.6)"; g.lineJoin = "round";
  g.strokeText(text, 64, 62); g.fillStyle = "#ffffff"; g.fillText(text, 64, 62);
  if (text === "6" || text === "9") { g.fillRect(44, 106, 40, 8); }
  var tex = new THREE.CanvasTexture(cv);
  texCache[text] = tex;
  return tex;
}

function buildDie(spec) {
  var geo = flatten(makeGeometry(spec.sides));
  var faces = clusterFaces(geo);
  var labels = assignLabels(faces, spec.labels);
  var group = new THREE.Group();
  var body = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ color: new THREE.Color(spec.color), roughness: 0.38, metalness: 0.12, flatShading: true }));
  group.add(body);
  group.add(new THREE.LineSegments(new THREE.EdgesGeometry(geo, 1), new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.4 })));
  var k = { 4: 0.8, 6: 0.9, 8: 0.8, 10: 0.62, 12: 1.0, 20: 0.8 }[spec.sides] || 0.8;
  faces.forEach(function (f, idx) {
    var size = Math.sqrt(f.area) * k;
    var plane = new THREE.Mesh(new THREE.PlaneGeometry(size, size),
      new THREE.MeshBasicMaterial({ map: labelTexture(labels[idx]), transparent: true, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2 }));
    plane.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(f.right, f.up, f.normal));
    plane.position.copy(f.center).addScaledVector(f.normal, 0.004);
    group.add(plane);
  });
  var targetIdx = labels.indexOf(spec.target);
  if (targetIdx < 0) targetIdx = 0;
  return { group: group, faces: faces, labels: labels, targetIdx: targetIdx, qFinal: finalQuaternion(faces[targetIdx]) };
}

window.__DICE_TEST__ = { buildDie: buildDie, d10Geometry: d10Geometry, clusterFaces: clusterFaces, flatten: flatten, finalQuaternion: finalQuaternion, TILT: TILT };

/* ---------- interface (HUD) ---------- */
function renderHud() {
  hudCaption.textContent = SPEC.caption || "";
  hudFoot.innerHTML = "";
  var tw = document.createElement("div"); tw.className = "totals";
  if (!SPEC.idle) {
    (SPEC.totals || []).forEach(function (tt) {
      var t = document.createElement("div"); t.className = "total";
      var lab = document.createElement("span"); lab.textContent = tt.label;
      var val = document.createElement("b"); val.textContent = String(tt.value);
      t.appendChild(lab); t.appendChild(val); tw.appendChild(t);
    });
  }
  hudFoot.appendChild(tw);
  var wrap = document.createElement("div"); wrap.className = "chips";
  SPEC.groups.forEach(function (g) {
    if (SPEC.idle) return;
    var chip = document.createElement("div"); chip.className = "chip"; chip.style.borderColor = g.color;
    var name = (g.label ? g.label + " · " : "") + g.values.length + "d" + g.sides + ": ";
    var vals = g.values.join(", ") + (g.extra ? " … (+" + g.extra + ")" : "");
    chip.textContent = name + vals;
    wrap.appendChild(chip);
  });
  hudFoot.appendChild(wrap);
  hudNote.textContent = SPEC.note || "";
}

function showFallback(msg) {
  fallback.style.display = "flex";
  fallback.textContent = msg;
  stage.style.display = "none";
  renderHud();
  hudFoot.style.opacity = 1;
}

/* ---------- cena ---------- */
function start() {
  if (typeof THREE === "undefined") { showFallback("Biblioteca 3D indisponível (sem acesso ao CDN). Resultados mostrados em texto."); return; }
  var renderer;
  try {
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  } catch (e) { showFallback("WebGL indisponível neste navegador. Resultados mostrados em texto."); return; }
  var W = stage.clientWidth || 400;
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setSize(W, HEIGHT);
  stage.appendChild(renderer.domElement);

  var scene = new THREE.Scene();
  var camera = new THREE.PerspectiveCamera(38, W / HEIGHT, 0.1, 100);
  scene.add(new THREE.AmbientLight(0xffffff, 0.75));
  var key = new THREE.DirectionalLight(0xffffff, 0.9); key.position.set(-3, 6, 7); scene.add(key);
  var rim = new THREE.DirectionalLight(0x8899ff, 0.35); rim.position.set(5, -2, 4); scene.add(rim);

  var n = SPEC.dice.length;
  var cols = n <= 3 ? n : (n <= 8 ? Math.ceil(n / 2) : 6);
  var rows = Math.ceil(n / cols), gap = 2.9;
  var dice = SPEC.dice.map(function (d, i) {
    var die = buildDie(d);
    var col = i % cols, row = Math.floor(i / cols);
    var inRow = Math.min(cols, n - row * cols);
    die.rest = new THREE.Vector3((col - (inRow - 1) / 2) * gap, ((rows - 1) / 2 - row) * gap, 0);
    die.axis = new THREE.Vector3(Math.random() - 0.5, Math.random() - 0.5, Math.random() - 0.5).normalize();
    die.spin = (7 + Math.random() * 5) * Math.PI;
    die.delay = i * 90;
    die.from = new THREE.Vector3(-W / 90 - 3, -2.5 - Math.random(), 1.5);
    scene.add(die.group);
    return die;
  });

  function fit() {
    var w = stage.clientWidth || W;
    renderer.setSize(w, HEIGHT);
    camera.aspect = w / HEIGHT; 
    var halfW = (cols * gap) / 2 + 0.4, halfH = (rows * gap) / 2 + 0.2;
    var t = Math.tan(camera.fov * Math.PI / 360);
    var dist = Math.max(halfH / t, halfW / (t * camera.aspect)) + 2;
    camera.position.set(0, 0, dist);
    camera.updateProjectionMatrix();
  }
  fit();
  window.addEventListener("resize", fit);

  var played = false;
  try {
    var k2 = "ms_rolled_" + SPEC.id;
    played = !!window.sessionStorage.getItem(k2);
    window.sessionStorage.setItem(k2, "1");
  } catch (e) { played = false; }
  if (SPEC.idle) played = true;

  renderHud();
  var DURATION = 1500, t0 = performance.now();
  var revealed = false;
  function reveal() { if (!revealed) { revealed = true; hudFoot.style.opacity = 1; } }
  if (played) reveal(); else hudFoot.style.opacity = 0;

  var tmp = new THREE.Quaternion();
  function frame(now) {
    var elapsed = now - t0, allDone = true;
    dice.forEach(function (d) {
      var t = played ? 1 : Math.max(0, Math.min(1, (elapsed - d.delay) / DURATION));
      if (t < 1) allDone = false;
      var p = 1 - Math.pow(1 - t, 3);              // ease-out
      var hop = Math.sin(Math.PI * Math.min(1, t * 1.15)) * 1.3 * (1 - p);
      d.group.position.copy(d.from).lerp(d.rest, p);
      d.group.position.y += hop;
      tmp.setFromAxisAngle(d.axis, d.spin * (1 - p));
      d.group.quaternion.copy(tmp).multiply(d.qFinal);   // em t=1 é exatamente qFinal
      if (SPEC.idle) d.group.rotation.y += 0.01;
    });
    renderer.render(scene, camera);
    if (allDone && !SPEC.idle) reveal();
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
}

try { start(); } catch (err) { showFallback("Falha ao iniciar a cena 3D. Resultados mostrados em texto."); }
})();
"""

HTML = """<!doctype html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
html,body{margin:0;padding:0;background:transparent;font-family:Inter,Segoe UI,Arial,sans-serif;color:#ececf1;overflow:hidden}
#wrap{position:relative;background:radial-gradient(ellipse at 50% 35%,#252838 0%,#14151c 75%);border:1px solid #30323d;border-radius:12px;overflow:hidden}
#stage{width:100%;display:block}
#stage canvas{display:block;margin:0 auto}
#cap{position:absolute;top:8px;left:12px;font-size:12px;color:#b8bacb;letter-spacing:.02em;max-width:70%;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
#foot{position:absolute;left:0;right:0;bottom:6px;display:flex;align-items:flex-end;justify-content:space-between;gap:8px;padding:0 10px;transition:opacity .35s ease;pointer-events:none}
.totals{display:flex;gap:6px}
.total{display:flex;flex-direction:column;align-items:center;background:#0f1016cc;border:1px solid #6d4aff;border-radius:10px;padding:2px 12px}
.total span{font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:#aab}
.total b{font-size:28px;line-height:1.05;color:#fff;text-shadow:0 0 12px #6d4aff}
.chips{display:flex;flex-wrap:wrap;gap:4px;justify-content:flex-end;max-width:75%}
.chip{font-size:11px;background:#0f1016cc;border:1px solid #444;border-radius:8px;padding:2px 7px;max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
#note{position:absolute;top:8px;right:12px;font-size:10px;color:#e0a02f;max-width:45%;text-align:right}
#fallback{display:none;min-height:__MINH__px;align-items:center;justify-content:center;text-align:center;padding:16px;color:#e0a02f;font-size:13px}
</style></head>
<body><div id="wrap" style="height:__HEIGHT__px">
<div id="cap"></div><div id="note"></div>
<div id="stage" style="height:__HEIGHT__px"></div>
<div id="fallback"></div>
<div id="foot"></div>
</div>
<script src="__THREE__"></script>
<script>__JS__</script>
</body></html>"""


def stage_html(spec, height=250):
    height = int(height)
    js = JS.replace("__SPEC__", _json_for_script(spec)).replace("__HEIGHT__", str(height - 4))
    return (HTML.replace("__THREE__", THREE_URL)
                .replace("__MINH__", str(height - 90))
                .replace("__HEIGHT__", str(height - 4))
                .replace("__JS__", js))
