import { useEffect, useRef } from 'react'
import * as THREE from 'three'

function makeLCG(seed = 42) {
  let s = seed >>> 0
  return () => {
    s = (Math.imul(1664525, s) + 1013904223) >>> 0
    return s / 0x100000000
  }
}

// Single hemisphere — the RIGHT hemisphere (outer at +x, medial/flat at -x).
// Mirror with rotation.y = Math.PI to create the left hemisphere.
function createHemisphereGeo() {
  const geo = new THREE.SphereGeometry(1.5, 84, 68)
  const pos = geo.attributes.position
  const arr = pos.array

  for (let i = 0; i < pos.count; i++) {
    const x0 = arr[i * 3], y0 = arr[i * 3 + 1], z0 = arr[i * 3 + 2]
    const len = Math.sqrt(x0 * x0 + y0 * y0 + z0 * z0) || 1e-9
    const nx = x0 / len, ny = y0 / len, nz = z0 / len

    const phi   = Math.acos(Math.max(-1, Math.min(1, ny)))
    const theta = Math.atan2(nz, nx)

    // Cortical folds — low frequency so ridges are few and clearly visible
    let fold = 0
    fold += 0.33 * Math.sin(2.5 * phi) * Math.cos(3.0 * theta)
    fold += 0.20 * Math.sin(4.0 * phi) * Math.cos(2.5 * theta + 1.2)
    fold += 0.12 * Math.sin(5.5 * phi) * Math.cos(4.0 * theta + 0.8)
    fold += 0.07 * Math.sin(7.5 * phi) * Math.cos(3.5 * theta + 2.0)
    fold += 0.04 * Math.sin(10.0 * phi) * Math.cos(5.5 * theta + 1.5)

    // Medial (inner) face: suppress folds and pull flat toward x = 0
    // nx < 0 means the vertex faces inward (toward the interhemispheric fissure)
    const medial = Math.max(0, -nx)        // 0 at outer face, 1 at innermost
    fold *= (1 - medial * 0.88)

    const r = 1.5 * (1 + fold)

    // Brain proportions: wider laterally, shorter vertically
    let x = nx * r * 1.10
    let y = ny * r * 0.82
    let z = nz * r * 1.02

    // Pull medial face toward x = 0 (creates a clean flat medial surface)
    if (nx < 0) x *= (1 - medial * 0.86)

    arr[i * 3] = x; arr[i * 3 + 1] = y; arr[i * 3 + 2] = z
  }

  pos.needsUpdate = true
  geo.computeVertexNormals()
  return geo
}

// Neurons distributed in bilateral clusters (left and right hemispheres)
function buildNeurons(rng, count = 54) {
  const neurons = []
  let attempts = 0
  while (neurons.length < count && attempts < 30000) {
    attempts++
    const side = neurons.length % 2 === 0 ? 1 : -1
    const cx = side * 0.80   // hemisphere centre
    const dx = (rng() * 2 - 1) * 1.35
    const dy = (rng() * 2 - 1) * 1.22
    const dz = (rng() * 2 - 1) * 1.18
    if ((dx / 1.35) ** 2 + (dy / 1.22) ** 2 + (dz / 1.18) ** 2 > 0.82) continue
    neurons.push([cx + dx, dy, dz])
  }

  const maxConn  = 4
  const connCount = new Array(neurons.length).fill(0)
  const connections = []

  for (let i = 0; i < neurons.length; i++) {
    for (let j = i + 1; j < neurons.length; j++) {
      if (connCount[i] >= maxConn || connCount[j] >= maxConn) continue
      const [ax, ay, az] = neurons[i], [bx, by, bz] = neurons[j]
      const d = Math.sqrt((ax - bx) ** 2 + (ay - by) ** 2 + (az - bz) ** 2)
      // Only axons within the same hemisphere — no cross-fissure connections
      if (d < 1.35 && neurons[i][0] * neurons[j][0] > 0) {
        connections.push([i, j])
        connCount[i]++; connCount[j]++
      }
    }
  }
  return { neurons, connections }
}

const SPARK_COLORS = [0x22d3ee, 0xa78bfa, 0xf472b6, 0x34d399, 0x60a5fa, 0xfbbf24]

export default function HoloBrainBackground() {
  const canvasRef = useRef()

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.setSize(window.innerWidth, window.innerHeight)

    const scene  = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(48, window.innerWidth / window.innerHeight, 0.1, 100)
    camera.position.set(0, 0, 11)

    scene.add(new THREE.AmbientLight(0xffffff, 0.05))

    // Aurora orbital point lights
    const ORBIT_CFG = [
      { color: 0x22d3ee, r: 6.5, speed: 0.33, phase: 0 },
      { color: 0xa78bfa, r: 5.4, speed: -0.24, phase: Math.PI * 0.7 },
      { color: 0xf472b6, r: 7.2, speed: 0.18, phase: Math.PI * 1.4 },
      { color: 0x34d399, r: 4.8, speed: -0.39, phase: Math.PI * 0.3 },
    ]
    const orbitLights = ORBIT_CFG.map(({ color, r, speed, phase }) => {
      const light = new THREE.PointLight(color, 2.8, 12)
      scene.add(light)
      return { light, r, speed, phase }
    })

    // ── Brain group ────────────────────────────────────────────────────────
    const group = new THREE.Group()
    group.position.set(2.0, 0.15, 0)
    group.rotation.x = -0.22    // tilt so the top (fissure) is visible
    scene.add(group)

    // Hemisphere geometry shared by both sides
    const hemiGeo = createHemisphereGeo()

    // Translucent brain surface (DoubleSide handles the mirrored left hemisphere)
    const surfaceMat = new THREE.MeshStandardMaterial({
      color: 0x6d28d9,
      emissive: 0x4c1d95,
      emissiveIntensity: 0.3,
      transparent: true,
      opacity: 0.065,
      side: THREE.DoubleSide,
      depthWrite: false,
    })

    // EdgesGeometry only shows edges where adjacent faces differ by > 10°
    // This highlights gyral ridges / sulcal grooves without the lat-lon globe grid
    const wireMat      = new THREE.LineBasicMaterial({ color: 0x818cf8, transparent: true, opacity: 0.24 })
    const rightEdgesGeo = new THREE.EdgesGeometry(hemiGeo, 10)
    const leftEdgesGeo  = new THREE.EdgesGeometry(hemiGeo, 10)

    // Right hemisphere
    const rightSurface = new THREE.Mesh(hemiGeo, surfaceMat)
    rightSurface.position.x = 0.4
    group.add(rightSurface)

    const rightEdges = new THREE.LineSegments(rightEdgesGeo, wireMat)
    rightEdges.position.x = 0.4
    group.add(rightEdges)

    // Left hemisphere — perfect bilateral mirror via Y rotation
    const leftSurface = new THREE.Mesh(hemiGeo, surfaceMat)
    leftSurface.position.x = -0.4
    leftSurface.rotation.y = Math.PI
    group.add(leftSurface)

    const leftEdges = new THREE.LineSegments(leftEdgesGeo, wireMat)
    leftEdges.position.x = -0.4
    leftEdges.rotation.y = Math.PI
    group.add(leftEdges)

    // Interhemispheric fissure — glowing tube running front-to-back at centre
    const fissPts = []
    for (let i = 0; i <= 36; i++) {
      const t = i / 36
      fissPts.push(new THREE.Vector3(0, -0.12 + Math.sin(t * Math.PI) * 0.28, (t - 0.5) * 3.4))
    }
    const fissCurve = new THREE.CatmullRomCurve3(fissPts)
    const fissGeo   = new THREE.TubeGeometry(fissCurve, 36, 0.038, 6, false)
    const fissMat   = new THREE.MeshBasicMaterial({ color: 0x22d3ee, transparent: true, opacity: 0.38 })
    group.add(new THREE.Mesh(fissGeo, fissMat))

    // Soft inner glow core
    const coreGeo = new THREE.SphereGeometry(0.9, 18, 18)
    const coreMat = new THREE.MeshStandardMaterial({
      color: 0xa78bfa, emissive: 0x7c3aed, emissiveIntensity: 0.75,
      transparent: true, opacity: 0.045, depthWrite: false,
    })
    group.add(new THREE.Mesh(coreGeo, coreMat))

    // ── Neuron network ─────────────────────────────────────────────────────
    const rng = makeLCG(42)
    const { neurons, connections } = buildNeurons(rng)

    const nPosArr = new Float32Array(neurons.length * 3)
    const nColArr = new Float32Array(neurons.length * 3)
    const auroraColors = [
      [0.133, 0.827, 0.933],
      [0.655, 0.545, 0.980],
      [0.957, 0.447, 0.714],
      [0.204, 0.827, 0.600],
      [0.376, 0.647, 0.980],
    ]
    neurons.forEach(([x, y, z], i) => {
      nPosArr[i * 3] = x; nPosArr[i * 3 + 1] = y; nPosArr[i * 3 + 2] = z
      const c = auroraColors[i % auroraColors.length]
      nColArr[i * 3] = c[0]; nColArr[i * 3 + 1] = c[1]; nColArr[i * 3 + 2] = c[2]
    })
    const neuronGeo = new THREE.BufferGeometry()
    neuronGeo.setAttribute('position', new THREE.BufferAttribute(nPosArr, 3))
    neuronGeo.setAttribute('color',    new THREE.BufferAttribute(nColArr, 3))
    const neuronMat = new THREE.PointsMaterial({
      size: 0.115, vertexColors: true, transparent: true, opacity: 0.90, sizeAttenuation: true,
    })
    group.add(new THREE.Points(neuronGeo, neuronMat))

    // Axon line segments
    const axonArr = []
    connections.forEach(([a, b]) => { axonArr.push(...neurons[a], ...neurons[b]) })
    const axonGeo = new THREE.BufferGeometry()
    axonGeo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(axonArr), 3))
    const axonMat = new THREE.LineBasicMaterial({ color: 0x818cf8, transparent: true, opacity: 0.12 })
    group.add(new THREE.LineSegments(axonGeo, axonMat))

    // ── Sparks — SLOW: 0.04–0.11 progress/s → ~6–14 s per axon ─────────
    const SPARK_COUNT  = 8
    const sparkGeo     = new THREE.SphereGeometry(0.065, 8, 8)
    const sparkMat     = new THREE.MeshBasicMaterial({ color: 0xffffff })
    const sparkMesh    = new THREE.InstancedMesh(sparkGeo, sparkMat, SPARK_COUNT)
    sparkMesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage)
    group.add(sparkMesh)

    const sparks = Array.from({ length: SPARK_COUNT }, (_, i) => {
      const color = new THREE.Color(SPARK_COLORS[i % SPARK_COLORS.length])
      sparkMesh.setColorAt(i, color)
      return {
        connIdx:  Math.floor(rng() * connections.length),
        progress: rng(),
        speed:    0.04 + rng() * 0.07,
        color,
      }
    })
    if (sparkMesh.instanceColor) sparkMesh.instanceColor.needsUpdate = true
    const dummy = new THREE.Object3D()

    // ── Aurora orbital rings ──────────────────────────────────────────────
    const RING_CFG = [
      { color: 0x22d3ee, r: 4.1, tube: 0.018, rot: [1.25, 0, 0.3] },
      { color: 0xf472b6, r: 4.6, tube: 0.012, rot: [1.88, 0, 1.2] },
      { color: 0xa78bfa, r: 3.7, tube: 0.010, rot: [0.62, 0.5, 2.1] },
    ]
    const ringMeshes = RING_CFG.map(({ color, r, tube, rot }) => {
      const m = new THREE.Mesh(
        new THREE.TorusGeometry(r, tube, 6, 128),
        new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.26 }),
      )
      m.rotation.set(...rot)
      group.add(m)
      return m
    })

    // Distant particle field
    const PART_COUNT  = 200
    const partPosArr  = new Float32Array(PART_COUNT * 3)
    for (let i = 0; i < PART_COUNT; i++) {
      const phi   = Math.acos(2 * rng() - 1)
      const theta = rng() * Math.PI * 2
      const r     = 3.8 + rng() * 2.6
      partPosArr[i * 3]     = r * Math.sin(phi) * Math.cos(theta)
      partPosArr[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta)
      partPosArr[i * 3 + 2] = r * Math.cos(phi)
    }
    const partGeo  = new THREE.BufferGeometry()
    partGeo.setAttribute('position', new THREE.BufferAttribute(partPosArr, 3))
    const partMat  = new THREE.PointsMaterial({ color: 0xa5b4fc, size: 0.05, transparent: true, opacity: 0.40, sizeAttenuation: true })
    const partMesh = new THREE.Points(partGeo, partMat)
    group.add(partMesh)

    // ── Animation loop ─────────────────────────────────────────────────────
    const clock = new THREE.Clock()
    let animId

    const animate = () => {
      animId = requestAnimationFrame(animate)
      const t = clock.getElapsedTime()

      // Slow majestic rotation — both hemispheres visible over time
      group.rotation.y = t * 0.08
      group.rotation.x = -0.22 + Math.sin(t * 0.13) * 0.05

      orbitLights.forEach(({ light, r, speed, phase }) => {
        const a = t * speed + phase
        light.position.set(
          group.position.x + Math.cos(a) * r,
          Math.sin(a * 0.55) * r * 0.38,
          Math.sin(a) * r,
        )
      })

      // Slow aurora colour shift on the wireframe
      wireMat.color.setHSL(((t * 0.020) % 1) * 0.22 + 0.57, 0.85, 0.68)

      // Spark pulses — SLOW
      sparks.forEach((s, idx) => {
        s.progress += s.speed * 0.016   // fixed dt so speed matches seconds
        if (s.progress >= 1.0) {
          s.connIdx  = Math.floor(rng() * connections.length)
          s.progress = 0
          s.speed    = 0.04 + rng() * 0.07
        }
        const [na, nb]     = connections[s.connIdx]
        const [ax, ay, az] = neurons[na]
        const [bx, by, bz] = neurons[nb]
        const p = s.progress
        dummy.position.set(ax + (bx - ax) * p, ay + (by - ay) * p, az + (bz - az) * p)
        dummy.scale.setScalar(1)
        dummy.updateMatrix()
        sparkMesh.setMatrixAt(idx, dummy.matrix)
      })
      sparkMesh.instanceMatrix.needsUpdate = true

      ringMeshes[0].rotation.z =  t * 0.047
      ringMeshes[1].rotation.z = -t * 0.037
      ringMeshes[2].rotation.y =  t * 0.054

      partMesh.rotation.y = t * 0.033

      renderer.render(scene, camera)
    }
    animate()

    const onResize = () => {
      camera.aspect = window.innerWidth / window.innerHeight
      camera.updateProjectionMatrix()
      renderer.setSize(window.innerWidth, window.innerHeight)
    }
    window.addEventListener('resize', onResize)

    return () => {
      cancelAnimationFrame(animId)
      window.removeEventListener('resize', onResize)
      hemiGeo.dispose()
      surfaceMat.dispose()
      wireMat.dispose()
      rightEdgesGeo.dispose()
      leftEdgesGeo.dispose()
      fissGeo.dispose()
      fissMat.dispose()
      coreGeo.dispose()
      coreMat.dispose()
      neuronGeo.dispose()
      neuronMat.dispose()
      axonGeo.dispose()
      axonMat.dispose()
      sparkGeo.dispose()
      sparkMat.dispose()
      partGeo.dispose()
      partMat.dispose()
      ringMeshes.forEach(m => { m.geometry.dispose(); m.material.dispose() })
      renderer.dispose()
    }
  }, [])

  return (
    <div className="fixed inset-0 z-0 pointer-events-none" aria-hidden="true" style={{ background: '#060b17' }}>
      <div className="aurora-blob aurora-blob-1" />
      <div className="aurora-blob aurora-blob-2" />
      <div className="aurora-blob aurora-blob-3" />
      <div className="aurora-blob aurora-blob-4" />
      <canvas
        ref={canvasRef}
        style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', opacity: 0.75 }}
      />
    </div>
  )
}
