import { useReveal } from '@/hooks/useReveal';

const STEPS = [
  {
    n: '01',
    t: 'Выбираете букет',
    d: 'В каталоге или по телефону. Можно просто назвать повод и бюджет — флорист предложит три варианта с фото.',
  },
  {
    n: '02',
    t: 'Мы собираем и показываем',
    d: 'Перед отправкой пришлём фото готового букета. Если что-то не нравится — поправим до идеала.',
  },
  {
    n: '03',
    t: 'Курьер везёт за 90 минут',
    d: 'По городу — в термобоксе с водой для стеблей. В непогоду цветы едут в защитной упаковке.',
  },
  {
    n: '04',
    t: 'Вручаем лично',
    d: 'Анонимно или от вашего имени, с открыткой, написанной от руки. Подтвердим доставку сообщением.',
  },
];

export default function Delivery() {
  const head = useReveal<HTMLDivElement>(0.2);
  const grid = useReveal<HTMLDivElement>(0.1);

  return (
    <section id="delivery" className="mx-auto max-w-7xl scroll-mt-24 px-5 py-20 md:px-8 md:py-28">
      <div ref={head.ref} className={`reveal ${head.visible ? 'visible' : ''} flex flex-wrap items-end justify-between gap-6`}>
        <div>
          <p className="micro-label mb-4 flex items-center gap-3 opacity-70">
            <span className="inline-block h-px w-10" style={{ background: 'var(--ink)' }} />
            Доставка
          </p>
          <h2 className="font-display text-[clamp(2.4rem,5.5vw,4.6rem)] font-medium leading-[1.02] tracking-[-0.02em]">
            Как это <em style={{ color: 'var(--terra)' }}>работает</em>
          </h2>
        </div>
        <p className="max-w-xs text-sm leading-relaxed opacity-70">
          Ежедневно с 8:00 до 22:00. Срочная доставка — от 45 минут в пределах центра.
        </p>
      </div>

      <div
        ref={grid.ref}
        className={`reveal ${grid.visible ? 'visible' : ''} mt-12 overflow-hidden rounded-2xl`}
        style={{ border: '1.5px solid var(--ink)', transitionDelay: '120ms' }}
      >
        <div className="grid grid-cols-1 md:grid-cols-2">
          {STEPS.map((s, i) => (
            <div
              key={s.n}
              className="p-7 md:p-9"
              style={{
                borderRight: i % 2 === 0 ? '1.5px solid var(--ink)' : 'none',
                borderBottom: i < 2 ? '1.5px solid var(--ink)' : 'none',
              }}
            >
              <div className="flex items-baseline gap-4">
                <span className="font-display text-5xl font-semibold italic" style={{ color: 'var(--terra)' }}>
                  {s.n}
                </span>
                <h3 className="font-display text-3xl font-semibold leading-tight">{s.t}</h3>
              </div>
              <p className="mt-4 max-w-md leading-relaxed opacity-75">{s.d}</p>
            </div>
          ))}
        </div>
        <div
          className="flex flex-wrap items-center justify-between gap-4 p-7 md:p-9"
          style={{ borderTop: '1.5px solid var(--ink)', background: 'var(--ink)', color: 'var(--paper)' }}
        >
          <p className="font-display text-2xl italic">
            Оплата картой онлайн, при получении или по счёту для компаний
          </p>
          <a href="#catalog" className="btn-terra">
            Выбрать букет <span className="arrow">→</span>
          </a>
        </div>
      </div>
    </section>
  );
}
