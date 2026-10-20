export type Category = 'roses' | 'peonies' | 'mono' | 'wild' | 'author' | 'season';

export interface Product {
  id: string;
  name: string;
  composition: string;
  price: number;
  oldPrice?: number;
  category: Category;
  image: string;
  tag?: string;
}

export const CATEGORIES: { id: Category | 'all'; label: string }[] = [
  { id: 'all', label: 'Все' },
  { id: 'roses', label: 'Розы' },
  { id: 'peonies', label: 'Пионы' },
  { id: 'mono', label: 'Монобукеты' },
  { id: 'wild', label: 'Полевые' },
  { id: 'author', label: 'Авторские' },
  { id: 'season', label: 'Сезонные' },
];

const u = (id: string, w = 900) =>
  `https://images.unsplash.com/${id}?q=80&w=${w}&auto=format&fit=crop`;

export const PRODUCTS: Product[] = [
  {
    id: 'velvet-waltz',
    name: 'Бархатный вальс',
    composition: '25 красных роз Freedom, итальянский рускус',
    price: 4900,
    category: 'roses',
    image: u('photo-1494972308805-463bc619d34e'),
    tag: 'Хит',
  },
  {
    id: 'provence-morning',
    name: 'Утро в Провансе',
    composition: 'Пионовидные розы, эустома, эвкалипт',
    price: 3800,
    category: 'roses',
    image: u('photo-1591886960571-74d43a9d4166'),
  },
  {
    id: 'north-orchid',
    name: 'Северная орхидея',
    composition: 'Белая фаленопсис-ветка в керамике',
    price: 5200,
    category: 'mono',
    image: u('photo-1454262041357-5d96f50a2f27'),
  },
  {
    id: 'dark-romance',
    name: 'Тёмный роман',
    composition: 'Протея, садовые розы, гиперикум',
    price: 6400,
    oldPrice: 7200,
    category: 'author',
    image: u('photo-1457089328109-e5d9bd499191'),
    tag: 'Выбор флориста',
  },
  {
    id: 'pink-calla',
    name: 'Калла',
    composition: '11 розовых калл, аспидистра',
    price: 4200,
    category: 'mono',
    image: u('photo-1469259943454-aa100abba749'),
  },
  {
    id: 'sunny-day',
    name: 'Солнечный день',
    composition: '7 подсолнухов, триколор, крафт',
    price: 2900,
    category: 'wild',
    image: u('photo-1470509037663-253afd7f0f51'),
  },
  {
    id: 'rainbow-fantasy',
    name: 'Радужная фантазия',
    composition: '15 радужных роз, люкс-упаковка',
    price: 7500,
    category: 'author',
    image: u('photo-1508610048659-a06b669e3321'),
    tag: 'Вау-эффект',
  },
  {
    id: 'one-rose',
    name: 'Минимализм',
    composition: 'Одна роза в стеклянной вазе',
    price: 990,
    category: 'mono',
    image: u('photo-1518895949257-7621c3c786d7'),
  },
  {
    id: 'sakura-garden',
    name: 'Вишнёвый сад',
    composition: 'Ветки цветущей сакуры, 5 шт',
    price: 3400,
    category: 'season',
    image: u('photo-1522748906645-95d8adfd52c7'),
    tag: 'Сезон',
  },
  {
    id: 'embrace',
    name: 'Объятия',
    composition: 'Пионы Sarah Bernhardt, фрезия, нарциссы',
    price: 5900,
    category: 'peonies',
    image: u('photo-1526047932273-341f2a7631f9'),
  },
  {
    id: 'orangery',
    name: 'Оранжерея',
    composition: 'Оранжевые розы, маттиола, ваза в подарок',
    price: 4600,
    category: 'author',
    image: u('photo-1533616688419-b7a585564566'),
  },
  {
    id: 'field-story',
    name: 'Полевая история',
    composition: 'Сухоцветы и полевые травы в крафте',
    price: 2400,
    category: 'wild',
    image: u('photo-1567696153798-9111f9cd3d0d'),
  },
];

export const HERO_TILES = [
  { src: u('photo-1526047932273-341f2a7631f9', 700), alt: 'Букет пионов в руках', caption: 'пионы · июнь' },
  { src: u('photo-1562690868-60bbe7293e94', 700), alt: 'Красная роза с каплями росы', caption: 'роса · утро' },
  { src: u('photo-1469259943454-aa100abba749', 700), alt: 'Розовые каллы', caption: 'каллы · моно' },
  { src: u('photo-1457089328109-e5d9bd499191', 700), alt: 'Авторский букет с протеей', caption: 'протея · авторское' },
  { src: u('photo-1519378058457-4c29a0a2efac', 700), alt: 'Поле красных цветов', caption: 'теплица · поставка' },
  { src: u('photo-1533616688419-b7a585564566', 700), alt: 'Букет в стеклянной вазе', caption: 'ваза · подарок' },
];

export const ABOUT_IMAGE = u('photo-1558350315-8aa00e8e4590', 1000);

export const fmtPrice = (n: number) =>
  n.toLocaleString('ru-RU') + ' ₽';
