export type SoundKind = "success" | "info" | "warning" | "alarm";

const presets: Record<SoundKind, { frequencies: number[]; duration: number; gap: number; gain: number }> = {
  success: { frequencies: [523.25, 659.25], duration: 0.12, gap: 0.12, gain: 0.18 },
  info: { frequencies: [440], duration: 0.1, gap: 0, gain: 0.14 },
  warning: { frequencies: [293.66, 293.66], duration: 0.13, gap: 0.18, gain: 0.2 },
  alarm: { frequencies: [392, 329.63, 261.63], duration: 0.12, gap: 0.12, gain: 0.24 }
};

export function playSound(kind: SoundKind, enabled: boolean) {
  if (!enabled || typeof window === "undefined") return;
  const AudioContextConstructor = window.AudioContext;
  if (!AudioContextConstructor) return;
  try {
    const context = new AudioContextConstructor();
    const preset = presets[kind];
    preset.frequencies.forEach((frequency, index) => {
      const start = context.currentTime + index * preset.gap;
      const oscillator = context.createOscillator();
      const gain = context.createGain();
      oscillator.type = "sine";
      oscillator.frequency.setValueAtTime(frequency, start);
      gain.gain.setValueAtTime(0.0001, start);
      gain.gain.exponentialRampToValueAtTime(preset.gain, start + 0.012);
      gain.gain.exponentialRampToValueAtTime(0.0001, start + preset.duration);
      oscillator.connect(gain);
      gain.connect(context.destination);
      oscillator.start(start);
      oscillator.stop(start + preset.duration + 0.02);
    });
    window.setTimeout(() => { void context.close().catch(() => undefined); }, 1000);
  } catch {
    // Audio is optional; unsupported or blocked audio must not break the ledger.
  }
}
