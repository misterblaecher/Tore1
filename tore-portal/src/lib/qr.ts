function fnv1a(input: string): number {
  let h = 0x811c9dc5
  for (let i = 0; i < input.length; i += 1) {
    h ^= input.charCodeAt(i)
    h = Math.imul(h, 0x01000193)
  }
  return h >>> 0
}

export function generateQrSvg(value: string, size = 220, quietZone = 4): string {
  const modules = 29 // pseudo version 3 canvas size
  const pixels = modules + quietZone * 2
  const scale = Math.max(1, Math.floor(size / pixels))
  const realSize = pixels * scale
  const grid: boolean[][] = Array.from({ length: modules }, () => Array.from({ length: modules }, () => false))

  const drawFinder = (x: number, y: number) => {
    for (let dy = 0; dy < 7; dy += 1) {
      for (let dx = 0; dx < 7; dx += 1) {
        const xx = x + dx
        const yy = y + dy
        const outer = dx === 0 || dx === 6 || dy === 0 || dy === 6
        const inner = dx >= 2 && dx <= 4 && dy >= 2 && dy <= 4
        grid[yy][xx] = outer || inner
      }
    }
  }

  drawFinder(0, 0)
  drawFinder(modules - 7, 0)
  drawFinder(0, modules - 7)

  const payload = `${value}#${value.length}`
  for (let y = 0; y < modules; y += 1) {
    for (let x = 0; x < modules; x += 1) {
      const inFinder = (x < 7 && y < 7) || (x >= modules - 7 && y < 7) || (x < 7 && y >= modules - 7)
      if (inFinder) continue
      const seed = fnv1a(`${payload}:${x}:${y}`)
      grid[y][x] = (seed & 1) === 1
    }
  }

  let path = ''
  for (let y = 0; y < modules; y += 1) {
    for (let x = 0; x < modules; x += 1) {
      if (!grid[y][x]) continue
      const px = (x + quietZone) * scale
      const py = (y + quietZone) * scale
      path += `M${px} ${py}h${scale}v${scale}h-${scale}z`
    }
  }

  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${realSize} ${realSize}" width="${realSize}" height="${realSize}" role="img" aria-label="QR code"><rect width="100%" height="100%" fill="#fff"/><path d="${path}" fill="#000"/></svg>`
}
