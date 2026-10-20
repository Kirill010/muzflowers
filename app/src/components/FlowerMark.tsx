export default function FlowerMark({ size = 30, color = '#064013' }: { size?: number; color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" aria-hidden="true">
      <g stroke={color} strokeWidth="1.6" strokeLinecap="round">
        {/* стебель */}
        <path d="M16 30 C16 24 16 20 16 15" />
        <path d="M16 24 C13 22 11 22.4 9.5 24" />
        <path d="M16 26.5 C19 25 20.5 25.4 22 27" />
        {/* лепестки */}
        <path d="M16 15 C13.5 12 13.5 8.5 16 5 C18.5 8.5 18.5 12 16 15 Z" fill={color} fillOpacity="0.14" />
        <path d="M16 15 C12 14.5 9 12 8.6 8 C12.6 8 15.2 10.8 16 15 Z" fill={color} fillOpacity="0.14" />
        <path d="M16 15 C20 14.5 23 12 23.4 8 C19.4 8 16.8 10.8 16 15 Z" fill={color} fillOpacity="0.14" />
        <circle cx="16" cy="13.4" r="1.3" fill={color} stroke="none" />
      </g>
    </svg>
  );
}
