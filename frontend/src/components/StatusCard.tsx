interface StatusCardProps {
  title: string;
  value: string;
  subtitle: string;
  tone: "o3" | "no2" | "neutral";
  eyebrow?: string;
  footnote?: string;
}

export function StatusCard({ title, value, subtitle, tone, eyebrow, footnote }: StatusCardProps) {
  return (
    <div className={`status-card ${tone}`}>
      {eyebrow ? <div className="status-eyebrow">{eyebrow}</div> : null}
      <div className="status-title">{title}</div>
      <div className="status-value">{value}</div>
      <div className="status-subtitle">{subtitle}</div>
      {footnote ? <div className="status-footnote">{footnote}</div> : null}
    </div>
  );
}
