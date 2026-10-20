import FlowerMark from '@/components/FlowerMark';

export default function Footer() {
  return (
    <footer
      id="contacts"
      className="scroll-mt-24 border-t"
      style={{ borderColor: 'var(--ink)', background: 'var(--ink)', color: 'var(--paper)' }}
    >
      <div className="mx-auto max-w-7xl px-5 pb-14 pt-20 md:px-8 md:pt-28">
        <div className="flex flex-wrap items-start justify-between gap-10">
          <div>
            <div className="flex items-center gap-3">
              <FlowerMark size={36} color="#f2edda" />
              <span className="font-display text-3xl font-semibold">Muzflowers</span>
            </div>
            <p className="font-display mt-5 max-w-sm text-2xl italic leading-snug opacity-80">
              Цветы, которые говорят за вас — каждый день с 2016 года.
            </p>
          </div>

          <div className="grid grid-cols-2 gap-14 md:gap-20">
            <div>
              <p className="micro-label mb-5" style={{ color: 'var(--terra)' }}>Магазин</p>
              <ul className="space-y-3 text-[0.95rem] opacity-85">
                <li><a className="transition-opacity hover:opacity-70" href="#catalog">Каталог</a></li>
                <li><a className="transition-opacity hover:opacity-70" href="#about">О нас</a></li>
                <li><a className="transition-opacity hover:opacity-70" href="#delivery">Доставка</a></li>
              </ul>
            </div>
            <div>
              <p className="micro-label mb-5" style={{ color: 'var(--terra)' }}>Контакты</p>
              <ul className="space-y-3 text-[0.95rem] opacity-85">
                <li><a className="transition-opacity hover:opacity-70" href="tel:+74950000000">+7 495 000-00-00</a></li>
                <li><a className="transition-opacity hover:opacity-70" href="mailto:hello@muzflowers.ru">hello@muzflowers.ru</a></li>
                <li>ул. Цветочная, 12 · 8:00–22:00</li>
                <li><a className="transition-opacity hover:opacity-70" href="#top">Telegram / WhatsApp</a></li>
              </ul>
            </div>
          </div>
        </div>

        <div
          className="font-display mt-20 select-none text-center text-[clamp(4rem,14vw,12rem)] font-semibold leading-none tracking-[-0.03em] opacity-[0.14]"
          aria-hidden="true"
        >
          muzflowers
        </div>

        <div className="mt-12 flex flex-wrap items-center justify-between gap-4 border-t pt-6 text-xs opacity-60" style={{ borderColor: 'rgba(242,237,218,0.2)' }}>
          <span>© 2016–2026 Muzflowers. Все права защищены.</span>
          <span>Фото: Unsplash. Сделано с любовью к цветам.</span>
        </div>
      </div>
    </footer>
  );
}
