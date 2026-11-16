/**
 * The bot's profile avatar.
 * By default (no emotion), renders the official static brand logo (/bot-avatar.svg) unchanged.
 * When an emotion is passed (used on chat reply and pending messages):
 * Renders the full-body Cyber Chef Bot companion:
 * - Hovering thruster with cyan glow
 * - Rounded aerodynamic torso with pulsing chest reactor core
 * - Expressive floating arms (cheering arms in victory when done, chin tap when slow)
 * - Digital OLED visor screen with laser HUD
 * - Antenna with live status LED
 * - Chef hat on top
 */

import { useEffect, useState } from "react";
import "./avatar.css";

export type BotEmotion = "idle" | "loading" | "slow" | "done" | "error";

export interface AvatarProps {
  size: "sm" | "md" | "xl";
  emotion?: BotEmotion;
  className?: string;
}

export function Avatar({ size, emotion, className = "" }: AvatarProps) {
  const px = { sm: 30, md: 40, xl: 88 }[size];

  // Keep the logo unchanged everywhere unless an emotion is explicitly requested (chat reply / pending)
  if (!emotion) {
    return (
      <img
        className={`avatar ${size} ${className}`.trim()}
        src="/bot-avatar.svg"
        alt=""
        width={px}
        height={px}
      />
    );
  }

  return <FullBodyCyberBot size={size} emotion={emotion} className={className} />;
}

function FullBodyCyberBot({
  size,
  emotion,
  className,
}: {
  size: "sm" | "md" | "xl";
  emotion: BotEmotion;
  className: string;
}) {
  const [currentEmotion, setCurrentEmotion] = useState<BotEmotion>(emotion);

  useEffect(() => {
    setCurrentEmotion(emotion);

    // If loading takes > 3.5s, automatically transition to slow
    if (emotion === "loading") {
      const timer = window.setTimeout(() => {
        setCurrentEmotion("slow");
      }, 3500);
      return () => window.clearTimeout(timer);
    }
  }, [emotion]);

  return (
    <div
      className={`avatar ${size} full-body-bot emotion-${currentEmotion} ${className}`.trim()}
      role="img"
      aria-label="Klean Nham Cyber Chef Bot"
    >
      <svg
        className="bot-svg"
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 100 115"
        aria-hidden="true"
      >
        <defs>
          {/* Visor clip */}
          <clipPath id={`visor-screen-clip-${size}`}>
            <rect x="28" y="42" width="44" height="24" rx="11" />
          </clipPath>
        </defs>

        {/* Robot Antenna (Angles behind chef hat) */}
        <g className="cyber-antenna">
          <line x1="64" y1="24" x2="73" y2="10" stroke="#B4C7F8" strokeWidth="2.4" strokeLinecap="round" />
          <circle cx="74" cy="9.5" r="4.5" fill="none" stroke="#38BDF8" strokeWidth="0.8" opacity="0.4" />
          <circle className="cyber-antenna-bulb" cx="74" cy="9.5" r="3" fill="#38BDF8" />
        </g>

        {/* Headphones / Ears with Cyber LED Status Rings */}
        <rect className="bot-ear left" x="16" y="47" width="8" height="16" rx="4" fill="#C9D5FF" />
        <circle className="cyber-ear-ring left" cx="20" cy="55" r="2.4" fill="none" stroke="#38BDF8" strokeWidth="1.2" />
        <circle cx="20" cy="55" r="1" fill="#38BDF8" />

        <rect className="bot-ear right" x="76" y="47" width="8" height="16" rx="4" fill="#C9D5FF" />
        <circle className="cyber-ear-ring right" cx="80" cy="55" r="2.4" fill="none" stroke="#38BDF8" strokeWidth="1.2" />
        <circle cx="80" cy="55" r="1" fill="#38BDF8" />

        {/* Complete Hovering Robot Body Group */}
        <g className="cyber-robot-full">
          {/* -------------------- 1. HOVER THRUSTER -------------------- */}
          <g className="cyber-thruster-group">
            <ellipse className="cyber-hover-mount" cx="50" cy="98" rx="11" ry="3" fill="#152052" />
            <ellipse className="cyber-thruster-beam" cx="50" cy="100" rx="8" ry="2.2" fill="#38BDF8" />
            <ellipse cx="50" cy="100" rx="3.5" ry="1" fill="#ffffff" />
          </g>

          {/* -------------------- 2. TORSO / BODY -------------------- */}
          {/* Aerodynamic White Ceramic Torso */}
          <rect className="cyber-torso" x="28" y="74" width="44" height="23" rx="11.5" fill="#ffffff" />

          {/* Chef Neck Collar Seam */}
          <path d="M 36 74 L 50 82 L 64 74" fill="none" stroke="#C9D5FF" strokeWidth="1.6" strokeLinecap="round" />

          {/* Glowing Chest Arc-Reactor Core (Heart of Bot) */}
          <g className="cyber-chest-group">
            <circle className="cyber-chest-ring" cx="50" cy="85" r="4.5" fill="none" stroke="#38BDF8" strokeWidth="1" opacity="0.6" />
            <circle className="cyber-chest-core" cx="50" cy="85" r="2.8" fill="#38BDF8" />
            <circle cx="50" cy="85" r="1.1" fill="#ffffff" />
          </g>

          {/* -------------------- 3. ARMS & HANDS -------------------- */}
          {currentEmotion === "done" ? (
            /* Celebration Victory Arms Raised High! \ ( ^o^ ) / */
            <g className="cyber-arms-cheer">
              <path className="cyber-arm-done left" d="M 28 78 Q 16 71 18 61" fill="none" stroke="#ffffff" strokeWidth="4.8" strokeLinecap="round" />
              <circle cx="18" cy="60" r="3.2" fill="#C9D5FF" />
              <path className="cyber-arm-done right" d="M 72 78 Q 84 71 82 61" fill="none" stroke="#ffffff" strokeWidth="4.8" strokeLinecap="round" />
              <circle cx="82" cy="60" r="3.2" fill="#C9D5FF" />
            </g>
          ) : currentEmotion === "slow" ? (
            /* Slow State: One Arm Tapping Chin Thoughtfully */
            <g className="cyber-arms-slow">
              <path className="cyber-arm left" d="M 28 77 Q 20 83 23 89" fill="none" stroke="#ffffff" strokeWidth="4.5" strokeLinecap="round" />
              <circle cx="23" cy="89" r="3" fill="#C9D5FF" />
              <path className="cyber-arm-chin right" d="M 72 78 Q 78 68 67 63" fill="none" stroke="#ffffff" strokeWidth="4.5" strokeLinecap="round" />
              <circle cx="66" cy="62" r="3" fill="#C9D5FF" />
            </g>
          ) : (
            /* Normal Resting / Floating Arms */
            <g className="cyber-arms-normal">
              <path className="cyber-arm left" d="M 28 77 Q 20 83 23 89" fill="none" stroke="#ffffff" strokeWidth="4.5" strokeLinecap="round" />
              <circle cx="23" cy="89" r="3" fill="#C9D5FF" />
              <path className="cyber-arm right" d="M 72 77 Q 80 83 77 89" fill="none" stroke="#ffffff" strokeWidth="4.5" strokeLinecap="round" />
              <circle cx="77" cy="89" r="3" fill="#C9D5FF" />
            </g>
          )}

          {/* -------------------- 4. NECK JOINT -------------------- */}
          <rect x="42" y="71" width="16" height="5" rx="2.5" fill="#C9D5FF" />
          <line x1="44" y1="73.5" x2="56" y2="73.5" stroke="#38BDF8" strokeWidth="1.2" strokeLinecap="round" />

          {/* -------------------- 5. HEAD & VISOR -------------------- */}
          {/* Ceramic White Robot Head */}
          <rect x="22" y="34" width="56" height="40" rx="16" fill="#ffffff" />

          {/* Dark Cyber OLED Visor Screen */}
          <rect x="28" y="42" width="44" height="24" rx="11" fill="#0C132E" />

          {/* Cyber Glass Border */}
          <rect
            x="29"
            y="43"
            width="42"
            height="22"
            rx="10"
            fill="none"
            stroke="rgba(56, 189, 248, 0.45)"
            strokeWidth="0.9"
          />

          {/* HUD Laser Scanline (When Loading / Answering) */}
          {currentEmotion === "loading" && (
            <g clipPath={`url(#visor-screen-clip-${size})`}>
              <line
                className="cyber-scan-laser"
                x1="28"
                y1="42"
                x2="72"
                y2="42"
                stroke="#38BDF8"
                strokeWidth="1.8"
                opacity="0.95"
              />
            </g>
          )}

          {/* -------------------- EYES -------------------- */}
          {currentEmotion === "done" ? (
            /* Done Checkmark Ticks (✓ ✓) */
            <>
              <path
                className="cyber-tick left"
                d="M 35 52 L 39 56 L 46 47"
                fill="none"
                stroke="#22C55E"
                strokeWidth="3.2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              <path
                className="cyber-tick right"
                d="M 54 52 L 58 56 L 65 47"
                fill="none"
                stroke="#22C55E"
                strokeWidth="3.2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              <path
                className="cyber-sparkle left"
                d="M 32 45 Q 33.5 45 33.5 43.5 Q 33.5 45 35 45 Q 33.5 45 33.5 46.5 Q 33.5 45 32 45 Z"
                fill="#FFE082"
              />
              <path
                className="cyber-sparkle right"
                d="M 65 44 Q 66.5 44 66.5 42.5 Q 66.5 44 68 44 Q 66.5 44 66.5 45.5 Q 66.5 44 65 44 Z"
                fill="#FFE082"
              />
              <ellipse className="cyber-blush left" cx="32" cy="57" rx="2.5" ry="1.4" fill="#FF7A8A" />
              <ellipse className="cyber-blush right" cx="68" cy="57" rx="2.5" ry="1.4" fill="#FF7A8A" />
            </>
          ) : currentEmotion === "error" ? (
            /* Crossed X X Eyes */
            <>
              <line x1="36" y1="48" x2="44" y2="56" stroke="#EF4444" strokeWidth="2.8" strokeLinecap="round" />
              <line x1="44" y1="48" x2="36" y2="56" stroke="#EF4444" strokeWidth="2.8" strokeLinecap="round" />
              <line x1="56" y1="48" x2="64" y2="56" stroke="#EF4444" strokeWidth="2.8" strokeLinecap="round" />
              <line x1="64" y1="48" x2="56" y2="56" stroke="#EF4444" strokeWidth="2.8" strokeLinecap="round" />
            </>
          ) : (
            /* Digital LED Eyes */
            <>
              <rect className="cyber-eye left" x="36.5" y="47.5" width="7" height="9" rx="1.8" fill="#FFC23D" />
              <rect className="cyber-eye right" x="56.5" y="47.5" width="7" height="9" rx="1.8" fill="#FFC23D" />
            </>
          )}

          {/* Coolant Sweat Drop (When Slow) */}
          {currentEmotion === "slow" && (
            <g className="cyber-coolant-drop">
              <path
                d="M 67 44 C 67 44 69.5 47 69.5 48.5 A 1.8 1.8 0 1 1 66 48.5 C 66 47 67 44 67 44 Z"
                fill="#38BDF8"
              />
              <path
                d="M 67.7 46.5 C 68.3 47.5 68.3 48.5 68 49"
                stroke="#ffffff"
                strokeWidth="0.5"
                strokeLinecap="round"
                fill="none"
                opacity="0.9"
              />
            </g>
          )}

          {/* -------------------- MOUTH -------------------- */}
          {currentEmotion === "done" ? (
            /* Wide Happy Smile */
            <path
              className="cyber-mouth done"
              d="M 43 60 Q 50 65 57 60"
              fill="none"
              stroke="#FFC23D"
              strokeWidth="2.8"
              strokeLinecap="round"
            />
          ) : currentEmotion === "loading" ? (
            /* Digital Equalizer Audio Soundwave (Speaking / Generating) */
            <g className="cyber-audio-wave">
              <line className="cyber-wave bar1" x1="44" y1="59" x2="44" y2="62" stroke="#FFC23D" strokeWidth="1.8" strokeLinecap="round" />
              <line className="cyber-wave bar2" x1="48" y1="58" x2="48" y2="63" stroke="#FFC23D" strokeWidth="1.8" strokeLinecap="round" />
              <line className="cyber-wave bar3" x1="52" y1="58" x2="52" y2="63" stroke="#FFC23D" strokeWidth="1.8" strokeLinecap="round" />
              <line className="cyber-wave bar4" x1="56" y1="59" x2="56" y2="62" stroke="#FFC23D" strokeWidth="1.8" strokeLinecap="round" />
            </g>
          ) : currentEmotion === "slow" ? (
            /* Puzzled Wavy Mouth */
            <path
              className="cyber-mouth slow"
              d="M 44 60.5 Q 47 58.5 50 60.5 T 56 60.5"
              fill="none"
              stroke="#FFC23D"
              strokeWidth="2"
              strokeLinecap="round"
            />
          ) : currentEmotion === "error" ? (
            /* Frown */
            <path
              className="cyber-mouth error"
              d="M 44 62 Q 50 58 56 62"
              fill="none"
              stroke="#EF4444"
              strokeWidth="2.4"
              strokeLinecap="round"
            />
          ) : (
            /* Friendly Smile */
            <path
              className="cyber-mouth idle"
              d="M 44 60.5 Q 50 63.5 56 60.5"
              fill="none"
              stroke="#FFC23D"
              strokeWidth="2.4"
              strokeLinecap="round"
            />
          )}

          {/* -------------------- 6. CHEF HAT -------------------- */}
          <circle cx="38" cy="22" r="8.5" fill="#ffffff" />
          <circle cx="50" cy="16" r="10.5" fill="#ffffff" />
          <circle cx="62" cy="22" r="8.5" fill="#ffffff" />
          <rect x="34" y="22" width="32" height="11" rx="2.5" fill="#ffffff" />
          <path d="M 34 31 h 32" stroke="#C9D5FF" strokeWidth="2.2" strokeLinecap="round" />
        </g>
      </svg>
    </div>
  );
}
