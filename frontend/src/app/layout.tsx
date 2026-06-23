/**
 * Root Layout - Only imports globals, no HTML structure
 */
import './globals.css';

export const metadata = {
  title: 'BookFinance',
  description: 'AI Financial Operating System',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
