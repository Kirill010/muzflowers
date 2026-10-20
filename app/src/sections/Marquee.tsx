const ITEMS = [
  'Свежая поставка каждое утро',
  'Доставка за 90 минут',
  'Соберём под повод и бюджет',
  'Открытка от руки — в подарок',
  'Фото букета перед отправкой',
  'Гарантия свежести 5 дней',
];

export default function Marquee() {
  const row = [...ITEMS, ...ITEMS];
  return (
    <div
      className="overflow-hidden border-y py-4"
      style={{ borderColor: 'var(--ink)', background: 'var(--ink)' }}
    >
      <div className="marquee-track">
        {[0, 1].map((half) => (
          <div key={half} className="flex shrink-0 items-center" aria-hidden={half === 1}>
            {row.slice(half * ITEMS.length, (half + 1) * ITEMS.length).map((item, i) => (
              <span
                key={i}
                className="font-display flex items-center text-xl italic md:text-2xl"
                style={{ color: 'var(--paper)' }}
              >
                <span className="px-6">{item}</span>
                <span style={{ color: 'var(--terra)' }}>✦</span>
              </span>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
