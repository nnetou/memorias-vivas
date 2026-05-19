/**
 * components/BottomNav.jsx — Barra de navegação inferior mobile-first.
 * Tabs: Início | Portfólio | Perfil
 */

const IconHome = ({ size = 26 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 9.5L12 3l9 6.5V20a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9.5z"/>
    <path d="M9 21V12h6v9"/>
  </svg>
);

const IconFolder = ({ size = 26 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
  </svg>
);

const IconUser = ({ size = 26 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
    <circle cx="12" cy="7" r="4"/>
  </svg>
);

const TABS = [
  { id: "inicio",    label: "Início",    Icon: IconHome },
  { id: "portfolio", label: "Portfólio", Icon: IconFolder },
  { id: "perfil",    label: "Perfil",    Icon: IconUser },
];

export default function BottomNav({ tabActiva, onChange }) {
  return (
    <nav className="bottom-nav" role="navigation" aria-label="Navegação principal">
      {TABS.map(({ id, label, Icon }) => {
        const activa = tabActiva === id;
        return (
          <button
            key={id}
            id={`nav-${id}`}
            aria-label={label}
            aria-current={activa ? "page" : undefined}
            onClick={() => onChange(id)}
            className={`bottom-nav-item${activa ? " active" : ""}`}
          >
            <Icon size={26} />
            <span>{label}</span>
          </button>
        );
      })}
    </nav>
  );
}
