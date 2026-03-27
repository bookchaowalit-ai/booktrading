import LandingPageClient from './LandingPageClient';

interface PageProps {
  params: Promise<{ lang: string }>;
}

export default async function LandingPage({ params }: PageProps) {
  const { lang } = await params;
  return <LandingPageClient lang={lang} />;
}
