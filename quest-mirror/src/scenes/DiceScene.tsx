/**
 * DiceScene — Three.js D20 with Rapier physics.
 *
 * A React Three Fiber canvas with an untextured D20 (obsidian material),
 * click-to-roll with physics simulation, and a 2D HUD overlay for results.
 * The die is a pure visual spectacle; face detection + label swap run
 * internally for battle scar recording, but no number textures are applied.
 *
 * Must be a default export for React.lazy() loading.
 */

import { useState, useEffect, useRef, useCallback, useMemo } from "react"
import { Canvas, useFrame } from "@react-three/fiber"
import { Physics, RigidBody, CuboidCollider } from "@react-three/rapier"
import type { RapierRigidBody } from "@react-three/rapier"
import type { DiceSceneProps, DicePhase } from "../dice/types.ts"
import { getClassConfig } from "../dice/classConfigs.ts"
import {
  detectTopFace,
  swapForResult,
  createFaceNumberMap,
} from "../dice/d20Faces.ts"

// ── Formula parser (shared with DiceRoller) ─────────────────────────
function parseFormula(formula: string) {
  const dieMatch = formula.match(/(\d*)d(\d+)/)
  const modMatch = formula.match(/[+-]\d+/)
  return {
    count: dieMatch ? parseInt(dieMatch[1] || "1", 10) : 1,
    dieSize: dieMatch ? parseInt(dieMatch[2], 10) : 20,
    modifier: modMatch ? parseInt(modMatch[0], 10) : 0,
  }
}

// ── D20 Die sub-component ───────────────────────────────────────────
interface D20Props {
  phase: DicePhase
  onSettle: (qx: number, qy: number, qz: number, qw: number) => void
  classConfig: ReturnType<typeof getClassConfig>
}

function D20Die({ phase, onSettle, classConfig }: D20Props) {
  const rigidBodyRef = useRef<RapierRigidBody>(null)
  const settleCountRef = useRef(0)

  // Apply impulse when phase transitions to "rolling"
  const prevPhaseRef = useRef<DicePhase>(phase)
  useEffect(() => {
    if (phase === "rolling" && prevPhaseRef.current !== "rolling") {
      const rb = rigidBodyRef.current
      if (!rb) return

      // Wake the body and reset velocities
      rb.wakeUp()
      rb.setLinvel({ x: 0, y: 0, z: 0 }, true)
      rb.setAngvel({ x: 0, y: 0, z: 0 }, true)

      // Random impulse: upward + slight lateral scatter
      const fx = (Math.random() - 0.5) * 4
      const fy = 6 + Math.random() * 3
      const fz = (Math.random() - 0.5) * 4
      rb.applyImpulse({ x: fx, y: fy, z: fz }, true)

      // Random torque for tumbling
      const tx = (Math.random() - 0.5) * 15
      const ty = (Math.random() - 0.5) * 15
      const tz = (Math.random() - 0.5) * 15
      rb.applyTorqueImpulse({ x: tx, y: ty, z: tz }, true)

      settleCountRef.current = 0
    }
    prevPhaseRef.current = phase
  }, [phase])

  // Detect settling: linvel + angvel both < 0.05 for ~30 consecutive frames
  useFrame(() => {
    if (phase !== "rolling") return
    const rb = rigidBodyRef.current
    if (!rb) return

    const lv = rb.linvel()
    const av = rb.angvel()
    const linSpeed = Math.sqrt(lv.x ** 2 + lv.y ** 2 + lv.z ** 2)
    const angSpeed = Math.sqrt(av.x ** 2 + av.y ** 2 + av.z ** 2)

    if (linSpeed < 0.05 && angSpeed < 0.05) {
      settleCountRef.current += 1
      if (settleCountRef.current >= 30) {
        const rot = rb.rotation()
        onSettle(rot.x, rot.y, rot.z, rot.w)
      }
    } else {
      settleCountRef.current = 0
    }
  })

  const mat = classConfig.material

  return (
    <RigidBody
      ref={rigidBodyRef}
      position={[0, 3, 0]}
      colliders="hull"
      restitution={0.3}
      friction={0.6}
      mass={1}
      linearDamping={0.3}
      angularDamping={0.2}
    >
      <mesh castShadow>
        <icosahedronGeometry args={[1, 0]} />
        <meshStandardMaterial
          color={mat.baseColor}
          roughness={mat.roughness}
          metalness={mat.metalness}
          emissive={mat.emissive ?? "#000000"}
          emissiveIntensity={mat.emissiveIntensity ?? 0}
        />
      </mesh>
    </RigidBody>
  )
}

// ── Arena — floor + 4 invisible walls ───────────────────────────────
function Arena() {
  return (
    <>
      {/* Floor */}
      <RigidBody type="fixed" position={[0, -0.5, 0]}>
        <CuboidCollider args={[6, 0.5, 6]} />
        <mesh receiveShadow>
          <boxGeometry args={[12, 1, 12]} />
          <meshStandardMaterial
            color="#1a1814"
            roughness={0.9}
            metalness={0.05}
          />
        </mesh>
      </RigidBody>

      {/* Walls — invisible colliders keeping the die in bounds */}
      {/* X-axis walls (left/right) */}
      <RigidBody type="fixed" position={[-6, 2, 0]}>
        <CuboidCollider args={[0.1, 4, 6]} />
      </RigidBody>
      <RigidBody type="fixed" position={[6, 2, 0]}>
        <CuboidCollider args={[0.1, 4, 6]} />
      </RigidBody>

      {/* Z-axis walls (front/back) — args=[6, 4, 0.1] per review fix */}
      <RigidBody type="fixed" position={[0, 2, -6]}>
        <CuboidCollider args={[6, 4, 0.1]} />
      </RigidBody>
      <RigidBody type="fixed" position={[0, 2, 6]}>
        <CuboidCollider args={[6, 4, 0.1]} />
      </RigidBody>
    </>
  )
}

// ── Camera positioned above the arena ───────────────────────────────
function DiceCamera() {
  useFrame(({ camera }) => {
    camera.position.set(0, 8, 6)
    camera.lookAt(0, 0, 0)
  })
  return null
}

// ── Main DiceScene (default export for React.lazy) ──────────────────
export default function DiceScene({
  formula,
  rollType: _rollType,
  prompt,
  requestId,
  autoTimeoutS,
  onResult,
  characterClass,
}: DiceSceneProps) {
  const [phase, setPhase] = useState<DicePhase>("ready")
  const [displayResult, setDisplayResult] = useState<number | null>(null)
  const [countdown, setCountdown] = useState(autoTimeoutS)

  // Stale-closure prevention refs (H9 pattern)
  const phaseRef = useRef<DicePhase>(phase)
  phaseRef.current = phase

  const onResultRef = useRef(onResult)
  onResultRef.current = onResult

  // Predetermine natural result on mount
  const { count, dieSize, modifier } = useMemo(() => parseFormula(formula), [formula])
  const predeterminedNatural = useMemo(() => {
    let total = 0
    for (let i = 0; i < count; i++) {
      total += Math.floor(Math.random() * dieSize) + 1
    }
    return total
  }, [count, dieSize])

  // Face-number map for label-swap logic (for scar recording)
  const faceMapRef = useRef(createFaceNumberMap())

  // Class config for material
  const classConfig = useMemo(() => getClassConfig(characterClass), [characterClass])

  // ── Roll trigger ────────────────────────────────────────────────
  const handleRoll = useCallback(() => {
    if (phaseRef.current !== "ready") return
    setPhase("rolling")
    setCountdown(0)
  }, [])

  // ── Keyboard support (Space / Enter) ────────────────────────────
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (phaseRef.current !== "ready") return
      if (e.key === " " || e.key === "Enter") {
        e.preventDefault()
        handleRoll()
      }
    }
    window.addEventListener("keydown", onKeyDown)
    return () => window.removeEventListener("keydown", onKeyDown)
  }, [handleRoll])

  // ── Auto-roll countdown ─────────────────────────────────────────
  useEffect(() => {
    if (autoTimeoutS <= 0) return

    const timer = setInterval(() => {
      // Use ref to avoid stale closure
      if (phaseRef.current !== "ready") {
        clearInterval(timer)
        return
      }
      setCountdown((prev) => {
        const next = prev - 1
        if (next <= 0) {
          handleRoll()
          return 0
        }
        return next
      })
    }, 1000)

    return () => clearInterval(timer)
  }, [autoTimeoutS, handleRoll])

  // ── Settle handler — face detection + result reporting ──────────
  const handleSettle = useCallback(
    (qx: number, qy: number, qz: number, qw: number) => {
      if (phaseRef.current !== "rolling") return
      setPhase("settling")

      // Detect which face is on top and swap for predetermined result
      const topIdx = detectTopFace(qx, qy, qz, qw)
      faceMapRef.current = swapForResult(
        faceMapRef.current,
        topIdx,
        predeterminedNatural,
      )

      const natural = predeterminedNatural
      const total = natural + modifier
      setDisplayResult(total)

      // Determine hold duration
      const isNat20 = dieSize === 20 && natural === 20
      const isNat1 = dieSize === 20 && natural === 1
      const holdMs = isNat20 || isNat1 ? 3000 : 800

      if (isNat20 || isNat1) {
        setPhase("ceremony")
      } else {
        setPhase("result")
      }

      // Report result after hold
      setTimeout(() => {
        setPhase("done")
        onResultRef.current(requestId, total, natural)
      }, holdMs)
    },
    [predeterminedNatural, modifier, dieSize, requestId],
  )

  // Derive display state
  const isNat20 =
    displayResult !== null && dieSize === 20 && predeterminedNatural === 20
  const isNat1 =
    displayResult !== null && dieSize === 20 && predeterminedNatural === 1

  return (
    <div
      style={{
        position: "relative",
        width: "100%",
        height: "100%",
        minHeight: "320px",
        background: "#0a0908",
        borderRadius: "0.5rem",
        overflow: "hidden",
      }}
    >
      {/* 3D Canvas */}
      <Canvas shadows>
        <DiceCamera />
        <ambientLight intensity={0.4} />
        <directionalLight
          position={[5, 10, 5]}
          intensity={1.2}
          castShadow
          shadow-mapSize-width={1024}
          shadow-mapSize-height={1024}
        />
        <pointLight position={[-3, 5, -3]} intensity={0.6} color="#c4a060" />
        <Physics gravity={[0, -9.81, 0]}>
          <Arena />
          <D20Die
            phase={phase}
            onSettle={handleSettle}
            classConfig={classConfig}
          />
        </Physics>
      </Canvas>

      {/* HUD Overlay — prompt, result, controls */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          pointerEvents: "none",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "1rem",
        }}
      >
        {/* Top: roll prompt */}
        <div
          style={{
            textAlign: "center",
            fontFamily: "var(--qm-font-narrative, Georgia, serif)",
            fontStyle: "italic",
            fontSize: "0.9375rem",
            color: "#d4c9a8",
            textShadow: "0 2px 8px rgba(0,0,0,0.6)",
            lineHeight: 1.4,
          }}
        >
          {prompt}
        </div>

        {/* Center: result display */}
        {displayResult !== null && (
          <div
            style={{
              textAlign: "center",
              alignSelf: "center",
            }}
          >
            <div
              style={{
                fontFamily:
                  "var(--qm-font-heading, 'Cormorant Garamond', Georgia, serif)",
                fontSize: "4rem",
                fontWeight: 700,
                color: isNat20
                  ? "#ffd700"
                  : isNat1
                    ? "#ff3333"
                    : "#d4c9a8",
                textShadow: isNat20
                  ? "0 0 20px rgba(255,215,0,0.6), 0 0 40px rgba(255,215,0,0.3)"
                  : isNat1
                    ? "0 0 20px rgba(255,51,51,0.6), 0 0 40px rgba(255,51,51,0.3)"
                    : "0 2px 12px rgba(0,0,0,0.8)",
                lineHeight: 1,
              }}
            >
              {displayResult}
            </div>
            {/* Show natural breakdown if modifier is present */}
            {displayResult !== predeterminedNatural && (
              <div
                style={{
                  fontFamily: "var(--qm-font-ui, sans-serif)",
                  fontSize: "0.875rem",
                  color: "#8a7e6e",
                  marginTop: "0.25rem",
                }}
              >
                nat {predeterminedNatural}
              </div>
            )}
            {/* Ceremony text */}
            {phase === "ceremony" && isNat20 && (
              <div
                style={{
                  fontFamily: "var(--qm-font-narrative, Georgia, serif)",
                  fontStyle: "italic",
                  fontSize: "1.125rem",
                  color: "#ffd700",
                  marginTop: "0.75rem",
                  textShadow: "0 0 12px rgba(255,215,0,0.4)",
                }}
              >
                Critical Success!
              </div>
            )}
            {phase === "ceremony" && isNat1 && (
              <div
                style={{
                  fontFamily: "var(--qm-font-narrative, Georgia, serif)",
                  fontStyle: "italic",
                  fontSize: "1.125rem",
                  color: "#ff3333",
                  marginTop: "0.75rem",
                  textShadow: "0 0 12px rgba(255,51,51,0.4)",
                }}
              >
                Critical Failure...
              </div>
            )}
          </div>
        )}

        {/* Bottom: roll button or countdown */}
        <div
          style={{
            textAlign: "center",
            pointerEvents: "auto",
          }}
        >
          {phase === "ready" && (
            <>
              <button
                onClick={handleRoll}
                style={{
                  padding: "0.5rem 1.5rem",
                  background: "var(--qm-accent, #8b1a1a)",
                  color: "#f5f0e8",
                  border: "none",
                  borderRadius: "0.375rem",
                  fontSize: "0.9375rem",
                  fontWeight: 600,
                  fontFamily: "var(--qm-font-ui, sans-serif)",
                  cursor: "pointer",
                  transition: "opacity 150ms, background 150ms",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background =
                    "var(--qm-accent-hover, #a52828)"
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background =
                    "var(--qm-accent, #8b1a1a)"
                }}
              >
                Cast the Bones
              </button>
              {countdown > 0 && (
                <div
                  style={{
                    fontFamily: "var(--qm-font-ui, sans-serif)",
                    fontSize: "0.75rem",
                    color: "#8a7e6e",
                    marginTop: "0.5rem",
                  }}
                >
                  auto in {countdown}s
                </div>
              )}
            </>
          )}
          {phase === "rolling" && (
            <div
              style={{
                fontFamily: "var(--qm-font-narrative, Georgia, serif)",
                fontStyle: "italic",
                fontSize: "0.875rem",
                color: "#8a7e6e",
              }}
            >
              The bones are cast...
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
