import type { Metadata, Viewport } from 'next';
import { asset } from '@/lib/caminhos';
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
      <head>
        {/* Fora do empacotamento de propósito: ver public/fonts.css. */}
        <link rel="stylesheet" href={asset('/fonts.css')} />
      </head>
      <body>{children}</body>
    </html>
  );
}
