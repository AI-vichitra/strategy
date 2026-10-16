'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Navbar from '@/components/Navbar';
import Hero from '@/components/Hero';
import FeaturesGrid from '@/components/FeaturesGrid';
import WorkflowFeature from '@/components/WorkflowFeature';
import FinalCTA from '@/components/FinalCTA';
import Footer from '@/components/Footer';

export default function Home() {
  const router = useRouter();
  const [checkingAuth, setCheckingAuth] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (token) {
      router.push('/build');
    } else {
      setCheckingAuth(false);
    }
  }, [router]);

  if (checkingAuth) {
    return (
      <main style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh', background: '#0b0a1d', color: '#fff' }}>
        <p>Verifying session...</p>
      </main>
    );
  }

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
