import PetalCanvas from '@/components/PetalCanvas';
import { HERO_TILES } from '@/data/products';
import { useReveal } from '@/hooks/useReveal';

/** Асимметричная мозаика: 12 колонок, разные span-ы и ритм отступов. */
const SPANS = [
  'col-span-6 md:col-span-3 md:row-span-2 aspect-[3/4] md:aspect-auto',
  'col-span-6 md:col-span-3 aspect-[3/4]',
  'col-span-6 md:col-span-3 md:row-span-2 aspect-[3/4] md:aspect-auto md:mt-14',
  'col-span-6 md:col-span-3 aspect-[3/4] md:mt-6',
  'col-span-6 md:col-span-3 aspect-[3/4] md:mt-[-2.5rem]',
  'col-span-6 md:col-span-3 aspect-[3/4] md:mt-10',
];

export default function Hero() {
  const title = useReveal<HTMLDivElement>(0.1);
  const mosaic = useReveal<HTMLDivElement>(0.05);

  return (
    <section id="top" className="relative overflow-hidden pt-28 md:pt-32">
      <PetalCanvas density={36} className="z-20" />

      <div className="relative z-10 mx-auto max-w-7xl px-5 md:px-8">
        <div
          ref={title.ref}
          className={`reveal ${title.visible ? 'visible' : ''} grid grid-cols-12 gap-6`}
        >
          <div className="col-span-12 md:col-span-8">
            <p className="micro-label mb-5 flex items-center gap-3 opacity-70">
              <span className="inline-block h-px w-10" style={{ background: 'var(--ink)' }} />
              Розничный цветочный магазин · с 2016 года
            </p>
            <h1 className="font-display text-[clamp(3.2rem,9.5vw,8.2rem)] font-medium leading-[0.95] tracking-[-0.02em]">
              Цветы,
              <br />
              которые{' '}
              <em className="font-medium" style={{ color: 'var(--terra)' }}>
                говорят
              </em>{' '}
              за вас
            </h1>
          </div>
          <div className="col-span-12 flex flex-col justify-end md:col-span-4 md:pb-4">
            <p className="max-w-sm text-[1.05rem] leading-relaxed opacity-80">
              Собираем букеты из утренней поставки и привозим за 90 минут.
              К каждому — открытка с вашими словами, написанная от руки.
            </p>
            <div className="mt-7 flex flex-wrap gap-3">
              <a href="#catalog" className="btn-major">
                Смотреть каталог <span className="arrow">→</span>
              </a>
              <a href="#delivery" className="btn-terra">
                Доставка <span className="arrow">→</span>
              </a>
            </div>
          </div>
        </div>

        {/* мозаика */}
        <div
          ref={mosaic.ref}
          className={`reveal ${mosaic.visible ? 'visible' : ''} mt-14 grid grid-cols-12 gap-4 pb-20 md:mt-20 md:gap-5`}
          style={{ transitionDelay: '150ms' }}
        >
          {HERO_TILES.map((t, i) => (
            <figure
              key={t.src}
              className={`group relative overflow-hidden rounded-2xl ${SPANS[i % SPANS.length]}`}
              style={{ border: '1px solid var(--line)' }}
            >
              <img
                src={t.src}
                alt={t.alt}
                loading={i < 3 ? 'eager' : 'lazy'}
                className="h-full w-full object-cover transition-transform duration-700 ease-out group-hover:scale-[1.05]"
              />
              <figcaption
                className="micro-label absolute bottom-3 left-3 rounded-full px-3 py-1.5 opacity-0 transition-opacity duration-300 group-hover:opacity-100"
                style={{ background: 'rgba(242,237,218,0.85)', backdropFilter: 'blur(6px)' }}
              >
                {t.caption}
              </figcaption>
            </figure>
          ))}
        </div>
      </div>
    </section>
  );
}
