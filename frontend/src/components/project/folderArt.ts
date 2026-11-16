/**
 * 生成手账 / 玻璃文件夹背后那层「液体」画面。
 * 移植自参考实现的 canvas 噪声场：两层域扭曲 + 坡面高光，低分辨率绘制后放大。
 */

function mulberry32(seed: number): () => number {
  let a = seed >>> 0
  return () => {
    a = (a + 0x6d2b79f5) >>> 0
    let t = a
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

function hashString(s: string): number {
  let h = 2166136261
  for (let i = 0; i < s.length; i++) h = Math.imul(h ^ s.charCodeAt(i), 16777619)
  return h >>> 0
}

function hexToRgb(hex: string): [number, number, number] {
  let h = hex.trim().replace(/^#/, '')
  if (h.length === 3) h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2]
  const n = /^[0-9a-f]{6}$/i.test(h) ? parseInt(h, 16) : 0x808080
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255]
}

type Recipe = { colors: string[]; scale: number; warp: number; angle: number; gloss: number; streak: number }

const RECIPES: Recipe[] = [
  { colors: ['#0b0d12', '#1d2330', '#3f4b63', '#7b8aa8', '#cfd8e6'], scale: 0.72, warp: 3.1, angle: -0.5, gloss: 0.5, streak: 0 },
  { colors: ['#120c18', '#3e2850', '#8f6c9c', '#b3502f', '#fbe7d2'], scale: 0.68, warp: 3.6, angle: 0.8, gloss: 0.45, streak: 0 },
  { colors: ['#07090c', '#16252c', '#3d5f68', '#a3201a', '#ff8a5c'], scale: 0.6, warp: 3.2, angle: -0.4, gloss: 0.55, streak: 0 },
  { colors: ['#0a0f1a', '#16243a', '#2f4d74', '#6f9ad3', '#e6f0ff'], scale: 0.75, warp: 1.5, angle: 0.35, gloss: 0.3, streak: 1 },
  { colors: ['#08120c', '#173024', '#4f7a5a', '#a7843a', '#fbf3d6'], scale: 0.7, warp: 3.4, angle: 2.1, gloss: 0.45, streak: 0 },
]

function makeFbm(seed: number, size = 64) {
  const r = mulberry32(seed)
  const grid = new Float32Array(size * size)
  for (let i = 0; i < grid.length; i++) grid[i] = r()
  const at = (x: number, y: number) => grid[(y & (size - 1)) * size + (x & (size - 1))]
  const smooth = (t: number) => t * t * (3 - 2 * t)
  const noise = (x: number, y: number) => {
    const xi = Math.floor(x)
    const yi = Math.floor(y)
    const xf = smooth(x - xi)
    const yf = smooth(y - yi)
    const a = at(xi, yi) + (at(xi + 1, yi) - at(xi, yi)) * xf
    const b = at(xi, yi + 1) + (at(xi + 1, yi + 1) - at(xi, yi + 1)) * xf
    return a + (b - a) * yf - 0.5
  }
  return (x: number, y: number, octaves: number) => {
    let sum = 0
    let amp = 0.55
    for (let i = 0; i < octaves; i++) {
      sum += amp * noise(x, y)
      const nx = 1.7 * x + 1.1 * y + 5.3
      y = -1.1 * x + 1.7 * y + 2.9
      x = nx
      amp *= 0.5
    }
    return sum
  }
}

const cache = new Map<string, HTMLCanvasElement>()

/** 画一张液体底图，按 key 缓存。 */
export function paintFolderArt(key: string, w: number, h: number): HTMLCanvasElement {
  const hit = cache.get(key)
  if (hit) return hit

  const seed = hashString(key)
  const recipe = RECIPES[seed % RECIPES.length]
  const r = mulberry32(seed + 7)
  const fbm = makeFbm(seed * 977 + 13)
  const ox = r() * 40
  const oy = r() * 40
  const ca = Math.cos(recipe.angle)
  const sa = Math.sin(recipe.angle)

  const gw = 72
  const gh = 58
  const field = new Float32Array(gw * gh)
  const qv = new Float32Array(gw * gh)
  let lo = Infinity
  let hi = -Infinity

  for (let gy = 0; gy < gh; gy++) {
    for (let gx = 0; gx < gw; gx++) {
      const u = (gx / gw - 0.5) * 2
      const v = (gy / gh - 0.5) * 2
      let px = (u * ca - v * sa) * recipe.scale
      let py = (u * sa + v * ca) * recipe.scale
      if (recipe.streak) {
        px *= 0.14
        py *= 2.2
      }
      px += ox
      py += oy
      const qx = fbm(px, py, 3)
      const qy = fbm(px + 5.2, py + 1.3, 3)
      const rx = fbm(px + recipe.warp * qx + 1.7, py + recipe.warp * qy + 9.2, 3)
      const ry = fbm(px + recipe.warp * qx + 8.3, py + recipe.warp * qy + 2.8, 3)
      const f = fbm(px + recipe.warp * rx, py + recipe.warp * ry, 4)
      const i = gy * gw + gx
      field[i] = f
      qv[i] = Math.sqrt(qx * qx + qy * qy)
      if (f < lo) lo = f
      if (f > hi) hi = f
    }
  }

  const canvas = document.createElement('canvas')
  canvas.width = gw
  canvas.height = gh
  const ctx = canvas.getContext('2d')
  if (!ctx) return canvas
  const img = ctx.createImageData(gw, gh)
  const stops = recipe.colors.map((c, i) => ({ t: i / (recipe.colors.length - 1), c: hexToRgb(c) }))
  const span = hi - lo || 1

  for (let gy = 0; gy < gh; gy++) {
    for (let gx = 0; gx < gw; gx++) {
      const i = gy * gw + gx
      let t = (field[i] - lo) / span
      t = t < 0 ? 0 : t > 1 ? 1 : t
      let j = 1
      while (j < stops.length - 1 && stops[j].t < t) j++
      const a = stops[j - 1]
      const b = stops[j]
      let f = (t - a.t) / (b.t - a.t || 1)
      f = f < 0 ? 0 : f > 1 ? 1 : f
      f = f * f * (3 - 2 * f)
      const gxv = field[gx < gw - 1 ? i + 1 : i] - field[gx > 0 ? i - 1 : i]
      const gyv = field[gy < gh - 1 ? i + gw : i] - field[gy > 0 ? i - gw : i]
      const nx = -gxv * 9
      const ny = -gyv * 9
      const nd = (nx * -0.55 + ny * -0.65 + 0.52) / Math.sqrt(nx * nx + ny * ny + 1)
      const spec = Math.pow(nd > 0 ? nd : 0, 22) * recipe.gloss * 255
      const silk = 1 + 0.05 * Math.sin(t * 90 + qv[i] * 20)
      const lit = (0.8 + 0.3 * nd) * silk
      img.data[i * 4] = Math.min(255, (a.c[0] + (b.c[0] - a.c[0]) * f) * lit + spec)
      img.data[i * 4 + 1] = Math.min(255, (a.c[1] + (b.c[1] - a.c[1]) * f) * lit + spec)
      img.data[i * 4 + 2] = Math.min(255, (a.c[2] + (b.c[2] - a.c[2]) * f) * lit + spec)
      img.data[i * 4 + 3] = 255
    }
  }
  ctx.putImageData(img, 0, 0)

  const out = document.createElement('canvas')
  out.width = w
  out.height = h
  const octx = out.getContext('2d')
  if (!octx) return canvas
  octx.imageSmoothingEnabled = true
  octx.imageSmoothingQuality = 'high'
  octx.drawImage(canvas, 0, 0, w, h)
  cache.set(key, out)
  return out
}
