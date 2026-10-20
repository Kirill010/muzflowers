import { useEffect, useState } from 'react';
import FlowerMark from '@/components/FlowerMark';
import { useCart } from '@/hooks/useCart';

const NAV = [
  { href: '#catalog', label: 'Каталог' },
  { href: '#about', label: 'О нас' },
  { href: '#delivery', label: 'Доставка' },
  { href: '#contacts', label: 'Контакты' },
];

export default function Header() {
  const { count, open } = useCart();
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  return (
    <header
      className={`fixed inset-x-0 top-0 z-50 transition-all duration-300 ${
        scrolled ? 'border-b' : 'border-b border-transparent'
      }`}
      style={{
        borderColor: scrolled ? 'var(--line)' : 'transparent',
        background: scrolled ? 'rgba(242, 237, 218, 0.82)' : 'transparent',
        backdropFilter: scrolled ? 'blur(14px) saturate(1.3)' : 'none',
      }}
    >
      <div className="mx-auto flex max-w-7xl items-center justify-between px-5 py-4 md:px-8">
        <a href="#top" className="flex items-center gap-2.5">
          <FlowerMark size={30} />
          <span className="font-display text-2xl font-semibold tracking-tight">Muzflowers</span>
        </a>

        <nav className="hidden items-center gap-8 md:flex">
          {NAV.map((n) => (
            <a
              key={n.href}
              href={n.href}
              className="micro-label opacity-80 transition-opacity hover:opacity-100"
            >
              {n.label}
            </a>
          ))}
        </nav>

        <button
          onClick={open}
          className="btn-major !px-5 !py-2.5"
          aria-label="Открыть корзину"
        >
          Корзина
          {count > 0 && (
            <span
              className="grid h-6 min-w-6 place-items-center rounded-full px-1 text-[0.72rem] font-extrabold"
              style={{ background: 'var(--terra)', color: 'var(--paper)' }}
            >
              {count}
            </span>
          )}
        </button>
      </div>
    </header>
  );
}
