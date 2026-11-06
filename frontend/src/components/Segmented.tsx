/** A row of mutually exclusive options (radio group), e.g. Light / Dark / Auto. */
export interface SegmentedOption<T extends string> {
  value: T;
  label: string;
  lang?: string;
}

export function Segmented<T extends string>({
  options,
  value,
  onChange,
  labelledBy,
}: {
  options: SegmentedOption<T>[];
  value: T;
  onChange: (value: T) => void;
  labelledBy: string;
}) {
  return (
    <div className="segmented" role="radiogroup" aria-labelledby={labelledBy}>
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          lang={o.lang}
          aria-checked={o.value === value}
          onClick={() => onChange(o.value)}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
