import Navbar from '@/components/Navbar';
import Hero from '@/components/Hero';
import FeaturesGrid from '@/components/FeaturesGrid';
import WorkflowFeature from '@/components/WorkflowFeature';
import FinalCTA from '@/components/FinalCTA';
import Footer from '@/components/Footer';

export default function Home() {
  return (
    <>
      <Navbar />
      <main>
        {/* 1. Hero — dark */}
        <Hero />

        {/* 2. Features grid — light */}
        <FeaturesGrid />

        {/* 3. Workflow — dark */}
        <WorkflowFeature />

        {/* 4. Final CTA — dark */}
        <FinalCTA />
      </main>

      {/* Footer — dark */}
      <Footer />
    </>
  );
}
