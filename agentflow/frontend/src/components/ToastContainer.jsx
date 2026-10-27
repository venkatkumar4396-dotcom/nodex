/**
 * ToastContainer — floating toast notifications for user actions and execution updates.
 */
import useStore from '../store';
import { IconCheck, IconClose, IconAlertTriangle, IconSparkles } from './Icons';

export default function ToastContainer() {
  const toasts = useStore((s) => s.toasts);
  const removeToast = useStore((s) => s.removeToast);

  if (toasts.length === 0) return null;

  return (
    <div className="af-toast-container">
      {toasts.map((t) => (
        <div key={t.id} className={`af-toast af-toast--${t.type}`} onClick={() => removeToast(t.id)}>
          <span className="af-toast__icon">
            {t.type === 'success' && <IconCheck size={13} />}
            {t.type === 'error' && <IconClose size={13} />}
            {t.type === 'warning' && <IconAlertTriangle size={13} />}
            {t.type === 'info' && <IconSparkles size={13} />}
          </span>
          <span className="af-toast__message">{t.message}</span>
          <button className="af-toast__close" onClick={(e) => { e.stopPropagation(); removeToast(t.id); }}>
            <IconClose size={11} />
          </button>
        </div>
      ))}
    </div>
  );
}
