/** A thin score bar: the fill is the value, the track is the whole scale. The number is always shown as text. */
export function Meter({ value, max = 1, label }: { value: number; max?: number; label?: string }) {
  const pct = max ? Math.max(0, Math.min(1, value / max)) * 100 : 0;
  const text = label ?? value.toFixed(2);
  return (
    <span className="demo-meter-wrap">
      <span className="demo-meter" title={text}>
        <span className="demo-meter-fill" style={{ width: `${pct}%` }} />
      </span>
      <span className="demo-num">{text}</span>
    </span>
  );
}
