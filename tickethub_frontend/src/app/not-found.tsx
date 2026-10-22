import Link from 'next/link';
export default function NotFound() {
    return <main className="container section">
  <h1>404</h1>
  <p>Страница не найдена / Page not found</p>
  <Link className="btn btn-primary" href="/ru">Tickethub</Link>
    </main>;
}
