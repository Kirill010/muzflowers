import Header from '@/sections/Header';
import Hero from '@/sections/Hero';
import Marquee from '@/sections/Marquee';
import Catalog from '@/sections/Catalog';
import About from '@/sections/About';
import Delivery from '@/sections/Delivery';
import Footer from '@/sections/Footer';
import CartDrawer from '@/sections/CartDrawer';

export default function Home() {
  return (
    <div className="paper-grain relative min-h-screen">
      <Header />
      <main>
        <Hero />
        <Marquee />
        <Catalog />
        <About />
        <Delivery />
      </main>
      <Footer />
      <CartDrawer />
    </div>
  );
}
