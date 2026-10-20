import PetalCanvas from '@/components/PetalCanvas';
import { ABOUT_IMAGE } from '@/data/products';
import { useReveal } from '@/hooks/useReveal';

const STATS = [
  { n: '9 лет', t: 'собираем букеты с 2016 года' },
  { n: '42 000+', t: 'доставленных букетов' },
  { n: '90 мин', t: 'среднее время доставки' },
  { n: '5 дней', t: 'гарантия свежести' },
];

export default function About() {
  const a = useReveal<HTMLDivElement>(0.15);
  const b = useReveal<HTMLDivElement>(0.15);

  return (
    <section
      id="about"
      className="relative scroll-mt-24 border-y py-20 md:py-28"
      style={{ borderColor: 'var(--line)', background: 'var(--paper-deep)' }}
    >
      <PetalCanvas density={16} className="z-0 opacity-70" />
      <div className="relative z-10 mx-auto grid max-w-7xl grid-cols-12 gap-8 px-5 md:px-8">
        <div
          ref={a.ref}
          className={`reveal ${a.visible ? 'visible' : ''} col-span-12 md:col-span-5`}
        >
          <div className="overflow-hidden rounded-2xl" style={{ border: '1px solid var(--line)' }}>
            <img
              src={ABOUT_IMAGE}
              alt="Фиолетовые цветы крупным планом"
              loading="lazy"
              className="aspect-[4/5] w-full object-cover"
            />
          </div>
          <p className="micro-label mt-4 opacity-60">наша теплица · поставщики · утро поставки</p>
        </div>

        <div
          ref={b.ref}
          className={`reveal ${b.visible ? 'visible' : ''} col-span-12 md:col-span-7 md:pl-6`}
          style={{ transitionDelay: '120ms' }}
        >
          <p className="micro-label mb-4 flex items-center gap-3 opacity-70">
            <span className="inline-block h-px w-10" style={{ background: 'var(--ink)' }} />
            О нас
          </p>
          <h2 className="font-display text-[clamp(2.2rem,4.8vw,4rem)] font-medium leading-[1.05] tracking-[-0.02em]">
            Мы верим, что букет — это <em style={{ color: 'var(--terra)' }}>письмо без слов</em>
          </h2>
          <p className="mt-7 max-w-xl text-[1.02rem] leading-relaxed opacity-80">
            Muzflowers начался с маленькой прилавочной точки у метро. Сегодня это мастерская,
            где пять флористов каждое утро встречают поставку, отбирают лучшие стебли
            и собирают букеты, которые не стыдно вручить и приятно получить.
          </p>
          <p className="mt-4 max-w-xl text-[1.02rem] leading-relaxed opacity-80">
            Мы не храним цветы неделями: что не продано за два дня — уходит в благотворительные
            букеты для городских больниц. Поэтому к вам всегда приезжает свежее.
          </p>

          <div className="mt-12 grid grid-cols-2 gap-px overflow-hidden rounded-2xl lg:grid-cols-4" style={{ border: '1px solid var(--line-strong)', background: 'var(--line-strong)' }}>
            {STATS.map((s) => (
              <div key={s.n} className="p-5" style={{ background: 'var(--paper)' }}>
                <div className="font-display text-4xl font-semibold" style={{ color: 'var(--terra)' }}>
                  {s.n}
                </div>
                <div className="mt-2 text-xs leading-snug opacity-70">{s.t}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
