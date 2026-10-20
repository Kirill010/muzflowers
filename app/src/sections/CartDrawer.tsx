import { useEffect, useState, type FormEvent } from 'react';
import { fmtPrice } from '@/data/products';
import { useCart } from '@/hooks/useCart';

export default function CartDrawer() {
  const { lines, total, isOpen, close, setQty, remove, clear, productOf } = useCart();
  const [exiting, setExiting] = useState(false);
  const [step, setStep] = useState<'cart' | 'done'>('cart');
  const [orderNo, setOrderNo] = useState('');
  const [form, setForm] = useState({ name: '', phone: '', address: '', time: '' });

  useEffect(() => {
    if (isOpen) {
      setExiting(false);
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [isOpen]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') requestClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const requestClose = () => {
    setExiting(true);
    window.setTimeout(() => {
      close();
      setExiting(false);
      if (step === 'done') setStep('cart');
    }, 240);
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    setOrderNo('MF-' + String(Math.floor(10000 + Math.random() * 90000)));
    clear();
    setStep('done');
  };

  if (!isOpen && !exiting) return null;

  const delivery = total >= 3000 || total === 0 ? 0 : 390;

  return (
    <div className="fixed inset-0 z-[80]" role="dialog" aria-modal="true" aria-label="Корзина">
      <div
        className={`absolute inset-0 ${exiting ? 'backdrop-exit' : 'backdrop-enter'}`}
        style={{ background: 'rgba(6,64,19,0.45)', backdropFilter: 'blur(3px)' }}
        onClick={requestClose}
      />
      <aside
        className={`absolute right-0 top-0 flex h-full w-full max-w-md flex-col ${exiting ? 'drawer-exit' : 'drawer-enter'}`}
        style={{ background: 'var(--paper)', borderLeft: '1.5px solid var(--ink)' }}
      >
        <div className="flex items-center justify-between border-b px-6 py-5" style={{ borderColor: 'var(--line)' }}>
          <h2 className="font-display text-3xl font-semibold">
            {step === 'done' ? 'Заказ оформлен' : 'Корзина'}
          </h2>
          <button onClick={requestClose} className="qty-btn !h-9 !w-9 text-lg" aria-label="Закрыть">
            ×
          </button>
        </div>

        {step === 'done' ? (
          <div className="flex flex-1 flex-col items-center justify-center px-8 text-center">
            <div
              className="grid h-20 w-20 place-items-center rounded-full text-3xl"
              style={{ background: 'var(--ink)', color: 'var(--paper)' }}
            >
              ✓
            </div>
            <p className="font-display mt-6 text-3xl font-semibold">Спасибо, {form.name || 'друг'}!</p>
            <p className="mt-3 leading-relaxed opacity-75">
              Заказ <b>{orderNo}</b> принят. Флорист позвонит на {form.phone || 'ваш номер'} в
              течение 10 минут, чтобы подтвердить детали.
            </p>
            <button onClick={requestClose} className="btn-major mt-8">
              Продолжить покупки <span className="arrow">→</span>
            </button>
          </div>
        ) : lines.length === 0 ? (
          <div className="flex flex-1 flex-col items-center justify-center px-8 text-center">
            <div className="font-display text-6xl opacity-30">❀</div>
            <p className="font-display mt-4 text-2xl font-semibold">Пока пусто</p>
            <p className="mt-2 text-sm opacity-65">Добавьте букет из каталога — он появится здесь.</p>
            <a href="#catalog" onClick={requestClose} className="btn-major mt-7">
              К каталогу <span className="arrow">→</span>
            </a>
          </div>
        ) : (
          <>
            <div className="flex-1 overflow-y-auto px-6 py-5">
              <ul className="space-y-4">
                {lines.map((l) => {
                  const p = productOf(l.id);
                  if (!p) return null;
                  return (
                    <li key={l.id} className="flex gap-4 rounded-2xl p-3" style={{ border: '1px solid var(--line)' }}>
                      <img
                        src={p.image}
                        alt={p.name}
                        className="h-20 w-20 shrink-0 rounded-xl object-cover"
                      />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-start justify-between gap-2">
                          <p className="font-display truncate text-lg font-semibold">{p.name}</p>
                          <button
                            onClick={() => remove(l.id)}
                            className="opacity-40 transition-opacity hover:opacity-100"
                            aria-label="Убрать"
                          >
                            ×
                          </button>
                        </div>
                        <p className="text-xs opacity-60">{fmtPrice(p.price)} / шт</p>
                        <div className="mt-2 flex items-center justify-between">
                          <div className="flex items-center gap-2.5">
                            <button className="qty-btn" onClick={() => setQty(l.id, l.qty - 1)} aria-label="Меньше">−</button>
                            <span className="w-5 text-center font-bold">{l.qty}</span>
                            <button className="qty-btn" onClick={() => setQty(l.id, l.qty + 1)} aria-label="Больше">+</button>
                          </div>
                          <span className="font-extrabold">{fmtPrice(p.price * l.qty)}</span>
                        </div>
                      </div>
                    </li>
                  );
                })}
              </ul>

              <form onSubmit={submit} className="mt-7 space-y-3">
                <p className="micro-label opacity-70">Оформление</p>
                <input
                  className="field"
                  placeholder="Ваше имя"
                  required
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                />
                <input
                  className="field"
                  placeholder="Телефон"
                  type="tel"
                  required
                  value={form.phone}
                  onChange={(e) => setForm({ ...form, phone: e.target.value })}
                />
                <input
                  className="field"
                  placeholder="Адрес доставки"
                  required
                  value={form.address}
                  onChange={(e) => setForm({ ...form, address: e.target.value })}
                />
                <input
                  className="field"
                  placeholder="Когда привезти (например, сегодня к 18:00)"
                  value={form.time}
                  onChange={(e) => setForm({ ...form, time: e.target.value })}
                />
                <button type="submit" className="btn-terra w-full justify-center !py-4">
                  Оформить заказ · {fmtPrice(total + delivery)}
                </button>
              </form>
            </div>

            <div className="border-t px-6 py-4 text-sm" style={{ borderColor: 'var(--line)' }}>
              <div className="flex justify-between opacity-75">
                <span>Букеты</span>
                <span>{fmtPrice(total)}</span>
              </div>
              <div className="mt-1 flex justify-between opacity-75">
                <span>Доставка {delivery === 0 && '(бесплатно от 3 000 ₽)'}</span>
                <span>{delivery === 0 ? '0 ₽' : fmtPrice(delivery)}</span>
              </div>
              <div className="mt-2 flex justify-between text-base font-extrabold">
                <span>Итого</span>
                <span>{fmtPrice(total + delivery)}</span>
              </div>
            </div>
          </>
        )}
      </aside>
    </div>
  );
}
