'use client';
export default function GlobalError({ reset }: {
    error: Error & {
        digest?: string;
    };
    reset: () => void;
}) {
    return <html lang="ru"><body><main style={{ fontFamily: 'Arial', padding: 32 }}>
      <h1>Tickethub</h1>
      <p>Не удалось открыть страницу. / Unable to open this page.</p>
      <button onClick={reset}>Повторить / Retry</button>
    </main></body></html>;
}
