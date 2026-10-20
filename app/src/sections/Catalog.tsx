import { useMemo, useState } from 'react';
import { CATEGORIES, PRODUCTS, fmtPrice, type Category, type Product } from '@/data/products';
import { useCart } from '@/hooks/useCart';
import { useReveal } from '@/hooks/useReveal';

/** Ритм асимметричной сетки на десктопе */
const SPAN_PATTERN = [
  'md:col-span-5',
  'md:col-span-7',
  'md:col-span-4',
  'md:col-span-4',
  'md:col-span-4',
  'md:col-span-8',
  'md:col-span-4',
  'md:col-span-6',
  'md:col-span-6',
  'md:col-span-4',
  'md:col-span-4',
  'md:col-span-4',
];

function ProductCard({ product, index }: { product: Product; index: number }) {
  const { add, open } = useCart();
  const { ref, visible } = useReveal<HTMLDivElement>(0.08);
  const [justAdded, setJustAdded] = useState(false);

  const handleAdd = () => {
    add(product.id);
    setJustAdded(true);
    window.setTimeout(() => setJustAdded(false), 900);
  };

  return (
    <div
      ref={ref}
      className={`reveal ${visible ? 'visible' : ''} col-span-12 ${SPAN_PATTERN[index % SPAN_PATTERN.length]}`}
      style={{ transitionDelay: `${(index % 3) * 90}ms` }}
    >
      <article className="product-card group h-full overflow-hidden rounded-2xl" style={{ border: '1px solid var(--line)', background: 'rgba(255,255,255,0.35)' }}>
        <div className="relative aspect-[4/3] overflow-hidden">
          <img
            src={product.image}
            alt={product.name}
            loading="lazy"
            className="h-full w-full object-cover transition-transform duration-700 ease-out group-hover:scale-[1.06]"
          />
          {product.tag && (
            <span
              className="micro-label absolute left-3 top-3 rounded-full px-3 py-1.5"
              style={{ background: 'var(--paper)', color: 'var(--ink)', border: '1px solid var(--line)' }}
            >
              {product.tag}
            </span>
          )}
          <button
            onClick={handleAdd}
            className="absolute bottom-3 right-3 translate-y-2 rounded-full px-4 py-2 text-[0.72rem] font-extrabold uppercase tracking-[0.12em] opacity-0 transition-all duration-200 group-hover:translate-y-0 group-hover:opacity-100"
            style={{ background: 'var(--ink)', color: 'var(--paper)' }}
          >
            {justAdded ? '✓ В корзине' : '+ В корзину'}
          </button>
        </div>

        <div className="flex items-start justify-between gap-4 p-5">
          <div>
            <h3 className="font-display text-2xl font-semibold leading-tight">{product.name}</h3>
            <p className="mt-1 text-sm opacity-65">{product.composition}</p>
          </div>
          <div className="shrink-0 text-right">
            {product.oldPrice && (
              <div className="text-sm line-through opacity-45">{fmtPrice(product.oldPrice)}</div>
            )}
            <div className="text-lg font-extrabold tracking-tight">{fmtPrice(product.price)}</div>
          </div>
        </div>

        <div className="flex items-center justify-between border-t px-5 py-3" style={{ borderColor: 'var(--line)' }}>
          <button onClick={open} className="micro-label opacity-60 transition-opacity hover:opacity-100">
            Оформить →
          </button>
          <button
            onClick={handleAdd}
            className="micro-label transition-colors"
            style={{ color: justAdded ? 'var(--terra)' : 'var(--ink)' }}
          >
            {justAdded ? '✓ Добавлено' : 'В корзину +'}
          </button>
        </div>
      </article>
    </div>
  );
}

export default function Catalog() {
  const [cat, setCat] = useState<Category | 'all'>('all');
  const head = useReveal<HTMLDivElement>(0.2);

  const list = useMemo(
    () => (cat === 'all' ? PRODUCTS : PRODUCTS.filter((p) => p.category === cat)),
    [cat]
  );

  return (
    <section id="catalog" className="mx-auto max-w-7xl scroll-mt-24 px-5 py-20 md:px-8 md:py-28">
      <div ref={head.ref} className={`reveal ${head.visible ? 'visible' : ''}`}>
        <div className="flex flex-wrap items-end justify-between gap-6">
          <div>
            <p className="micro-label mb-4 flex items-center gap-3 opacity-70">
              <span className="inline-block h-px w-10" style={{ background: 'var(--ink)' }} />
              Каталог · {PRODUCTS.length} букетов
            </p>
            <h2 className="font-display text-[clamp(2.4rem,5.5vw,4.6rem)] font-medium leading-[1.02] tracking-[-0.02em]">
              Собрано{' '}
              <em style={{ color: 'var(--terra)' }}>сегодня утром</em>
            </h2>
          </div>
          <p className="max-w-xs text-sm leading-relaxed opacity-70">
            Если нужного букета нет — напишите нам, соберём индивидуально под ваш повод и бюджет.
          </p>
        </div>

        <div className="mt-9 flex gap-2.5 overflow-x-auto pb-2 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          {CATEGORIES.map((c) => (
            <button
              key={c.id}
              className={`chip ${cat === c.id ? 'active' : ''}`}
              onClick={() => setCat(c.id)}
            >
              {c.label}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-10 grid grid-cols-12 gap-5 md:gap-6">
        {list.map((p, i) => (
          <ProductCard key={p.id} product={p} index={i} />
        ))}
      </div>
    </section>
  );
}
