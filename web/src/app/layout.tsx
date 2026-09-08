import type { Metadata, Viewport } from 'next';
import './fonts.css';
import './globals.css';

export const metadata: Metadata = {
  title: 'MAIA · Programação de manutenção',
  description: 'Piloto do agente programador de PCM',
};

export const viewport: Viewport = {
  themeColor: '#164194',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <body>{children}</body>
    </html>
  );
}
