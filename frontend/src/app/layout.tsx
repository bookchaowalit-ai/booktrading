/**
 * Root Layout - Only imports globals, no HTML structure
 */
import './globals.css';

export const metadata = {
  title: 'TradeBot Pro',
  description: 'Automated Trading System',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
