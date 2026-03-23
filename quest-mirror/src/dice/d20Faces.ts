/**
 * D20 face detection and predetermined result correction.
 *
 * Strategy (industry standard "label swap"):
 * 1. Physics runs naturally with random forces
 * 2. After dice settle, detect which face points up
 * 3. Swap the number-to-face mapping so the desired result appears on top
 * 4. For v1, the number displays as a HUD overlay (no face textures)
 *
 * Standard D20 rule: opposite faces sum to 21.
 */

const PHI = (1 + Math.sqrt(5)) / 2

// Icosahedron vertices (normalized)
const _v = [
  [0, 1, PHI], [0, -1, PHI], [0, 1, -PHI], [0, -1, -PHI],
  [1, PHI, 0], [-1, PHI, 0], [1, -PHI, 0], [-1, -PHI, 0],
  [PHI, 0, 1], [-PHI, 0, 1], [PHI, 0, -1], [-PHI, 0, -1],
].map(v => {
  const len = Math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)
  return [v[0] / len, v[1] / len, v[2] / len] as [number, number, number]
})

// 20 triangular faces (vertex index triples)
const FACE_INDICES: [number, number, number][] = [
  [0, 1, 8],  [0, 8, 4],  [0, 4, 5],  [0, 5, 9],  [0, 9, 1],
  [1, 6, 8],  [8, 6, 10], [8, 10, 4], [4, 10, 2], [4, 2, 5],
  [5, 2, 11], [5, 11, 9], [9, 11, 7], [9, 7, 1],  [1, 7, 6],
  [3, 6, 7],  [3, 7, 11], [3, 11, 2], [3, 2, 10], [3, 10, 6],
]

/** Pre-computed face center normals (unit vectors). */
export const FACE_NORMALS: [number, number, number][] = FACE_INDICES.map(
  ([a, b, c]) => {
    const cx = (_v[a][0] + _v[b][0] + _v[c][0]) / 3
    const cy = (_v[a][1] + _v[b][1] + _v[c][1]) / 3
    const cz = (_v[a][2] + _v[b][2] + _v[c][2]) / 3
    const len = Math.sqrt(cx * cx + cy * cy + cz * cz)
    return [cx / len, cy / len, cz / len] as [number, number, number]
  },
)

/**
 * Default face-index -> d20-number mapping.
 * Arranged so opposite faces sum to 21.
 */
export function createFaceNumberMap(): number[] {
  return [20, 2, 8, 14, 12, 18, 4, 16, 6, 10, 1, 19, 11, 13, 7, 9, 15, 3, 17, 5]
}

/**
 * Given a quaternion (from Rapier), find which face index points most upward.
 *
 * @param qx, qy, qz, qw — Quaternion components from rigid body rotation
 * @returns Face index (0-19)
 */
export function detectTopFace(qx: number, qy: number, qz: number, qw: number): number {
  let bestIdx = 0
  let bestDot = -Infinity

  for (let i = 0; i < FACE_NORMALS.length; i++) {
    const [nx, ny, nz] = FACE_NORMALS[i]

    // Rotate normal by quaternion: q * n * q^-1
    const ix = qw * nx + qy * nz - qz * ny
    const iy = qw * ny + qz * nx - qx * nz
    const iz = qw * nz + qx * ny - qy * nx
    const iw = -qx * nx - qy * ny - qz * nz

    const ry = iy * qw + iw * (-qy) + iz * (-qx) - ix * (-qz)

    if (ry > bestDot) {
      bestDot = ry
      bestIdx = i
    }
  }

  return bestIdx
}

/**
 * Compute the swapped face-number mapping so the desired result appears
 * on the face currently pointing up.
 *
 * @param currentMap — Current face-index -> number mapping
 * @param topFaceIdx — Which face index is pointing up
 * @param desiredNumber — The number we want on top (1-20)
 * @returns New mapping array (swap the two entries)
 */
export function swapForResult(
  currentMap: number[],
  topFaceIdx: number,
  desiredNumber: number,
): number[] {
  const newMap = [...currentMap]
  const currentTopNumber = newMap[topFaceIdx]

  if (currentTopNumber === desiredNumber) return newMap

  const desiredFaceIdx = newMap.indexOf(desiredNumber)

  newMap[topFaceIdx] = desiredNumber
  newMap[desiredFaceIdx] = currentTopNumber

  return newMap
}
