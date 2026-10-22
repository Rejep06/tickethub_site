'use client';
import { createContext, useCallback, useContext, useRef, useState, useEffect, type ReactNode } from 'react';
const Context = createContext<(text: string) => void>(() => {
});
export function ToastProvider({ children }: {
    children: ReactNode;
}) {
    const [message, setMessage] = useState('');
    const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
    const notify = useCallback((text: string) => {
        setMessage(text);
        if (timer.current)
            clearTimeout(timer.current);
        timer.current = setTimeout(() => setMessage(''), 4500);
    }, []);
    useEffect(() => () => {
        if (timer.current)
            clearTimeout(timer.current);
    }, []);
    return <Context.Provider value={notify}>
  {children}
  <div className="toast" role="status" aria-live="polite" hidden={!message}>{message}</div>
    </Context.Provider>;
}
export function useToast() {
    return useContext(Context);
}
